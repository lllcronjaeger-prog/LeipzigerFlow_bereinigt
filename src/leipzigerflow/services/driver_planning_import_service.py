from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from difflib import SequenceMatcher
import re
import unicodedata

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.modulon_resource_planner import ModulonPlanningPreview, ModulonPlanningRow
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.external_mapping import ExternalMapping
from leipzigerflow.models.resource_absence import DriverAbsence


@dataclass(slots=True)
class DriverPlanningImportResult:
    imported: int = 0
    periods_created: int = 0
    replaced: int = 0
    mappings_created: int = 0
    mappings_updated: int = 0
    unmatched: list[str] = field(default_factory=list)
    automatic_matches: list[str] = field(default_factory=list)
    unknown_statuses: set[str] = field(default_factory=set)


@dataclass(slots=True)
class DriverMatchCandidate:
    driver_id: int
    driver_name: str
    score: float
    reason: str


@dataclass(slots=True)
class UnmatchedDriverInfo:
    source_row: int
    driver_number: str
    personnel_number: str
    full_name: str
    external_id: str
    candidates: list[DriverMatchCandidate] = field(default_factory=list)


class DriverPlanningImportService:
    SOURCE = "Modulon Ressourcenplaner"
    MAPPING_SYSTEM = "Modulon"
    MAPPING_ENTITY = "driver"
    _SPECIAL_TRANSLATION = str.maketrans({
        "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ø": "o", "Ø": "o",
        "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
    })

    def __init__(self, session: Session):
        self.session = session
        self._mapping_cache: dict[tuple[str, str, str], ExternalMapping] = {}

    @classmethod
    def _normalized_words(cls, value: str) -> list[str]:
        text = (value or "").replace("\u00a0", " ").replace("\u200b", " ")
        text = text.translate(cls._SPECIAL_TRANSLATION)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.findall(r"[a-z0-9]+", text.casefold())

    @classmethod
    def _norm(cls, value: str) -> str:
        return "".join(cls._normalized_words(value))

    @classmethod
    def _name_match_score(cls, row: ModulonPlanningRow, driver: Driver) -> tuple[float, str]:
        row_first = cls._normalized_words(row.first_name)
        row_last = cls._normalized_words(row.last_name)
        driver_first = cls._normalized_words(driver.first_name)
        driver_last = cls._normalized_words(driver.last_name)
        if not row_first or not row_last or not driver_first or not driver_last:
            return 0.0, "unvollständiger Name"

        row_given = row_first[0]
        driver_given = driver_first[0]
        first_ratio = SequenceMatcher(None, row_given, driver_given).ratio()
        last_ratio = SequenceMatcher(None, "".join(row_last), "".join(driver_last)).ratio()

        if row_last == driver_last and row_given == driver_given:
            if row_first == driver_first:
                return 1.0, "Name exakt/normalisiert"
            return 0.995, "Zweitname abweichend"

        short, long = sorted((row_given, driver_given), key=len)
        if row_last == driver_last and len(short) >= 5 and long.startswith(short):
            return 0.97, "Vorname abgekürzt"

        # Typische einzelne Schreibfehler aus Fremdsystemen, z. B.
        # Schannnak ↔ Schannak. Nur bei sehr ähnlichem Vornamen und eindeutigem
        # Nachnamen-Treffer oberhalb einer strengen Schwelle zulassen.
        if first_ratio >= 0.92 and last_ratio >= 0.92:
            score = first_ratio * 0.35 + last_ratio * 0.65
            return score, "leichte Schreibabweichung"
        return 0.0, "Name weicht zu stark ab"

    @classmethod
    def _external_id(cls, row: ModulonPlanningRow) -> str:
        # Die Modulon-Fahrernummer ist der stabilste Schlüssel des Berichts.
        # Falls sie fehlt, wird die Personalnummer verwendet.
        return (row.driver_number or row.personnel_number or "").strip()

    def _mapped_driver(self, row: ModulonPlanningRow) -> Driver | None:
        external_id = self._external_id(row)
        if not external_id:
            return None
        mapping = self.session.scalar(select(ExternalMapping).where(
            ExternalMapping.source_system == self.MAPPING_SYSTEM,
            ExternalMapping.entity_type == self.MAPPING_ENTITY,
            ExternalMapping.external_id == external_id,
        ))
        if mapping is None:
            return None
        driver = self.session.get(Driver, mapping.internal_id)
        return driver if driver is not None and driver.active else None

    def _mapping_key(self, external_id: str) -> tuple[str, str, str]:
        return (self.MAPPING_SYSTEM, self.MAPPING_ENTITY, external_id)

    def _load_mapping_cache(self) -> None:
        self._mapping_cache = {
            self._mapping_key(mapping.external_id): mapping
            for mapping in self.session.scalars(select(ExternalMapping).where(
                ExternalMapping.source_system == self.MAPPING_SYSTEM,
                ExternalMapping.entity_type == self.MAPPING_ENTITY,
            ))
        }

    def _save_mapping(
        self,
        row: ModulonPlanningRow,
        driver: Driver,
        method: str,
    ) -> str | None:
        """Create or update an external mapping without duplicate pending INSERTs.

        The application session runs with ``autoflush=False``. Repeated day rows for
        the same driver therefore could not see a mapping added earlier in the same
        import and created multiple pending rows with the same unique key. The local
        cache is the source of truth for the whole transaction.
        """
        external_id = self._external_id(row)
        if not external_id:
            return None
        key = self._mapping_key(external_id)
        mapping = self._mapping_cache.get(key)
        action = "updated"
        if mapping is None:
            mapping = ExternalMapping(
                source_system=self.MAPPING_SYSTEM,
                entity_type=self.MAPPING_ENTITY,
                external_id=external_id,
                internal_id=driver.id,
            )
            self.session.add(mapping)
            self._mapping_cache[key] = mapping
            action = "created"
        mapping.internal_id = driver.id
        mapping.external_label = row.full_name
        mapping.match_method = method
        return action

    def _find_driver(self, row: ModulonPlanningRow) -> tuple[Driver | None, str]:
        mapped = self._mapped_driver(row)
        if mapped is not None:
            return mapped, "gespeicherte Modulon-Zuordnung"

        if row.personnel_number:
            candidates = list(self.session.scalars(select(Driver).where(
                Driver.personnel_number == row.personnel_number,
                Driver.active.is_(True),
            )))
            if len(candidates) == 1:
                return candidates[0], "Personalnummer"

        if row.driver_number:
            candidates = list(self.session.scalars(select(Driver).where(
                Driver.modulon_driver_number == row.driver_number,
                Driver.active.is_(True),
            )))
            if len(candidates) == 1:
                return candidates[0], "Modulon-Fahrernummer"

            normalized = row.driver_number.lstrip("0") or "0"
            candidates = list(self.session.scalars(select(Driver).where(
                or_(Driver.match_code == row.driver_number, Driver.match_code == normalized),
                Driver.active.is_(True),
            )))
            if len(candidates) == 1:
                return candidates[0], "Matchcode"

        scored: list[tuple[float, Driver, str]] = []
        for driver in self.session.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.id)):
            score, reason = self._name_match_score(row, driver)
            if score >= 0.92:
                scored.append((score, driver, reason))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        if not scored:
            return None, ""

        best_score, best_driver, reason = scored[0]
        # Automatische Zuordnung nur, wenn der beste Treffer klar besser als
        # ein möglicher zweiter Kandidat ist. So werden Namensvetter nicht
        # versehentlich zusammengeführt.
        if len(scored) > 1 and best_score - scored[1][0] < 0.04:
            return None, ""
        return best_driver, reason

    def _candidate_matches(self, row: ModulonPlanningRow, limit: int = 5) -> list[DriverMatchCandidate]:
        candidates: list[DriverMatchCandidate] = []
        for driver in self.session.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.id)):
            score, reason = self._name_match_score(row, driver)
            # Also offer weaker but useful same-surname suggestions for manual selection.
            if score <= 0:
                row_last = "".join(self._normalized_words(row.last_name))
                driver_last = "".join(self._normalized_words(driver.last_name))
                if row_last and driver_last:
                    last_ratio = SequenceMatcher(None, row_last, driver_last).ratio()
                    first_ratio = SequenceMatcher(
                        None,
                        (self._normalized_words(row.first_name) or [""])[0],
                        (self._normalized_words(driver.first_name) or [""])[0],
                    ).ratio()
                    score = first_ratio * 0.35 + last_ratio * 0.65
                    reason = "möglicher Namensähnlichkeitstreffer"
            if score >= 0.45:
                candidates.append(DriverMatchCandidate(int(driver.id), driver.full_name, score, reason))
        candidates.sort(key=lambda item: (-item.score, item.driver_name.casefold()))
        return candidates[:limit]

    def unmatched_drivers(self, preview: ModulonPlanningPreview) -> list[UnmatchedDriverInfo]:
        seen: set[tuple[str, str, str]] = set()
        result: list[UnmatchedDriverInfo] = []
        for row in preview.valid_rows:
            key = (row.driver_number, row.personnel_number, self._norm(row.full_name))
            if key in seen:
                continue
            seen.add(key)
            driver, _ = self._find_driver(row)
            if driver is not None:
                continue
            result.append(UnmatchedDriverInfo(
                source_row=row.source_row,
                driver_number=row.driver_number,
                personnel_number=row.personnel_number,
                full_name=row.full_name,
                external_id=self._external_id(row),
                candidates=self._candidate_matches(row),
            ))
        return result

    @staticmethod
    def _group_contiguous_rows(rows: list[tuple[ModulonPlanningRow, Driver, str]]):
        """Combine adjacent daily cells with the same status into periods."""
        ordered = sorted(rows, key=lambda item: (item[1].id, item[0].day, item[0].mapped_status, item[0].source_status))
        periods: list[list[tuple[ModulonPlanningRow, Driver, str]]] = []
        for item in ordered:
            row, driver, _ = item
            if periods:
                previous_row, previous_driver, _ = periods[-1][-1]
                same_series = (
                    previous_driver.id == driver.id
                    and previous_row.mapped_status == row.mapped_status
                    and previous_row.source_status == row.source_status
                    and previous_row.driver_group == row.driver_group
                    and previous_row.branch == row.branch
                    and row.day == previous_row.day + timedelta(days=1)
                )
                if same_series:
                    periods[-1].append(item)
                    continue
            periods.append([item])
        return periods

    def import_preview(
        self,
        preview: ModulonPlanningPreview,
        manual_mappings: dict[str, int] | None = None,
    ) -> DriverPlanningImportResult:
        result = DriverPlanningImportResult(unknown_statuses=set(preview.unknown_statuses))
        month_start = datetime.combine(preview.month, time.min)
        if preview.month.month == 12:
            next_month = preview.month.replace(year=preview.month.year + 1, month=1)
        else:
            next_month = preview.month.replace(month=preview.month.month + 1)
        month_end = datetime.combine(next_month, time.min)

        try:
            self._load_mapping_cache()
            existing = list(self.session.scalars(select(DriverAbsence).where(
                DriverAbsence.source == self.SOURCE,
                DriverAbsence.starts_at >= month_start,
                DriverAbsence.starts_at < month_end,
            )))
            result.replaced = len(existing)
            for item in existing:
                self.session.delete(item)

            unmatched_keys: set[str] = set()
            match_notes: set[str] = set()
            resolved_rows: dict[tuple[str, str, str], tuple[Driver | None, str]] = {}
            mapping_actions: dict[str, str] = {}
            matched_rows: list[tuple[ModulonPlanningRow, Driver, str]] = []
            manual_mappings = manual_mappings or {}
            for row in preview.valid_rows:
                cache_key = (row.driver_number, row.personnel_number, self._norm(row.full_name))
                if cache_key not in resolved_rows:
                    external_id = self._external_id(row)
                    manual_driver_id = manual_mappings.get(external_id) if external_id else None
                    if manual_driver_id is not None:
                        manual_driver = self.session.get(Driver, int(manual_driver_id))
                        resolved_rows[cache_key] = (manual_driver, "manuelle Zuordnung")
                    else:
                        resolved_rows[cache_key] = self._find_driver(row)
                driver, match_reason = resolved_rows[cache_key]
                if driver is None:
                    unmatched_keys.add(
                        f"Zeile {row.source_row}: {row.full_name or row.driver_number} "
                        f"(Modulon-ID {row.driver_number or 'fehlt'}, Personal-Nr. {row.personnel_number or 'fehlt'})"
                    )
                    continue
                external_id = self._external_id(row)
                if external_id not in mapping_actions:
                    action = self._save_mapping(row, driver, match_reason)
                    if action is not None:
                        mapping_actions[external_id] = action
                else:
                    # Keep label/method current without counting the same driver once
                    # per occupied day cell.
                    self._save_mapping(row, driver, match_reason)
                if match_reason not in {
                    "Personalnummer", "Modulon-Fahrernummer", "Matchcode",
                    "Name exakt/normalisiert", "gespeicherte Modulon-Zuordnung",
                }:
                    match_notes.add(f"Zeile {row.source_row}: {row.full_name} → {driver.full_name} ({match_reason})")
                if row.personnel_number and not driver.personnel_number:
                    driver.personnel_number = row.personnel_number
                if row.driver_number and not driver.modulon_driver_number:
                    driver.modulon_driver_number = row.driver_number
                matched_rows.append((row, driver, match_reason))
                result.imported += 1

            for period in self._group_contiguous_rows(matched_rows):
                first_row, driver, _ = period[0]
                last_row = period[-1][0]
                starts_at = datetime.combine(first_row.day, time.min)
                ends_at = datetime.combine(last_row.day + timedelta(days=1), time.min)
                metadata = [f"Modulon-Status: {first_row.source_status}"]
                if first_row.driver_group:
                    metadata.append(f"Modulon-Gruppe: {first_row.driver_group}")
                if first_row.branch:
                    metadata.append(f"Niederlassung: {first_row.branch}")
                self.session.add(DriverAbsence(
                    driver_id=driver.id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    reason=first_row.mapped_status,
                    remarks="; ".join(metadata),
                    active=True,
                    source=self.SOURCE,
                    source_key=(
                        f"{preview.month:%Y-%m}:{first_row.driver_number or first_row.personnel_number or self._norm(first_row.full_name)}:"
                        f"{first_row.day:%Y-%m-%d}:{last_row.day:%Y-%m-%d}"
                    ),
                ))
                result.periods_created += 1
            result.unmatched = sorted(unmatched_keys)
            result.automatic_matches = sorted(match_notes)
            result.mappings_created = sum(1 for action in mapping_actions.values() if action == "created")
            result.mappings_updated = sum(1 for action in mapping_actions.values() if action == "updated")
            # Explicit flush turns database constraint violations into a controlled
            # transaction failure before commit. The except block then rolls back the
            # complete monthly import.
            self.session.flush()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result
