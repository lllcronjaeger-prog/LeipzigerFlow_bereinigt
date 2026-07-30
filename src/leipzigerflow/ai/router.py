from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle


@dataclass(frozen=True, slots=True)
class DirectAnswer:
    """Deterministische Antwort, die ohne Sprachmodell erzeugt werden kann."""

    text: str
    source: str = "LeipzigerFlow-Datenbank"


class AiQueryRouter:
    """Beantwortet eindeutige Dispositionsfragen direkt aus der Datenbank.

    Fachbegriffe wie ``offen``, ``geplant`` oder ``ohne Fahrer`` werden nicht
    dem Sprachmodell zur Interpretation überlassen. Nur unklare oder echte
    Analysefragen fallen kontrolliert an Ollama zurück.
    """

    _COUNT_WORDS = ("wie viele", "anzahl", "wieviel", "wie viel")
    _ANALYSIS_WORDS = ("warum", "kritisch", "optimier", "empfehl", "verbesser", "analys")
    _CLOSED_TOUR_STATUSES = frozenset({"abgeschlossen", "erledigt", "storniert"})
    _AVAILABLE_RESOURCE_STATUSES = frozenset({"frei", "auf dem hof", "verfügbar"})

    def __init__(self, session: Session):
        self.session = session

    def answer(self, question: str) -> DirectAnswer | None:
        normalized = self._normalize(question)
        if not normalized:
            return None

        # Eindeutige Fachfragen zuerst behandeln – auch ohne "wie viele".
        if self._contains_any(normalized, "tour", "touren"):
            tour_answer = self._answer_tour_question(normalized)
            if tour_answer is not None:
                return tour_answer

        if self._contains_any(normalized, "auftrag", "aufträge", "transportauftrag", "transportaufträge"):
            order_answer = self._answer_order_question(normalized)
            if order_answer is not None:
                return order_answer

        resource_answer = self._answer_resource_availability(normalized)
        if resource_answer is not None:
            return resource_answer

        if not self._contains_any(normalized, *self._COUNT_WORDS):
            return None

        # Analytische Zusätze dürfen nicht durch eine zu einfache Anzahl ersetzt werden.
        if self._contains_any(normalized, *self._ANALYSIS_WORDS):
            return None

        if self._contains_any(normalized, "fahrzeug", "fahrzeuge", "lkw", "zugmaschine"):
            active, total = self._active_and_total(Vehicle, Vehicle.active)
            return DirectAnswer(self._format_active_total("Fahrzeuge", active, total))

        if self._contains_any(normalized, "fahrer", "fahrerinnen"):
            active, total = self._active_and_total(Driver, Driver.active)
            return DirectAnswer(self._format_active_total("Fahrer", active, total))

        if self._contains_any(normalized, "trailer", "auflieger"):
            active, total = self._active_and_total(Trailer, Trailer.active)
            return DirectAnswer(self._format_active_total("Trailer", active, total))

        if self._contains_any(normalized, "tour", "touren"):
            total = self._count(Tour)
            return DirectAnswer(f"In LeipzigerFlow sind aktuell {total} Touren gespeichert.")

        if self._contains_any(normalized, "auftrag", "aufträge", "transportauftrag", "transportaufträge"):
            total = self._count(TransportOrder)
            return DirectAnswer(f"In LeipzigerFlow sind aktuell {total} Transportaufträge gespeichert.")

        return None

    def _answer_tour_question(self, normalized: str) -> DirectAnswer | None:
        if self._contains_any(normalized, *self._ANALYSIS_WORDS):
            return None

        if self._contains_any(normalized, "ohne fahrer", "kein fahrer", "nicht mit fahrer"):
            count = self._count(Tour, Tour.driver_id.is_(None), self._tour_is_open_condition())
            return DirectAnswer(self._count_sentence(count, "offene Tour", "offene Touren", "ohne Fahrer"))

        if self._contains_any(normalized, "ohne fahrzeug", "kein fahrzeug", "ohne lkw", "kein lkw"):
            count = self._count(Tour, Tour.vehicle_id.is_(None), self._tour_is_open_condition())
            return DirectAnswer(self._count_sentence(count, "offene Tour", "offene Touren", "ohne Fahrzeug"))

        if self._contains_any(normalized, "offen", "offene", "nicht abgeschlossen"):
            return DirectAnswer(self._open_tours_answer())

        status_map = (
            (("ungeplant", "nicht geplant"), "Ungeplant"),
            (("geplant", "geplante"), "Geplant"),
            (("unterwegs", "in durchführung", "laufend"), "Unterwegs"),
            (("abgeschlossen", "erledigt", "fertig"), "Abgeschlossen"),
            (("storniert", "abgesagt"), "Storniert"),
        )
        for terms, status in status_map:
            if self._contains_any(normalized, *terms):
                count = self._count_status(Tour, status)
                label = "Tour" if count == 1 else "Touren"
                return DirectAnswer(f"Aktuell {self._verb(count)} {count} {label} mit dem Status „{status}“ vorhanden.")
        return None

    def _answer_order_question(self, normalized: str) -> DirectAnswer | None:
        if self._contains_any(normalized, *self._ANALYSIS_WORDS):
            return None
        if self._contains_any(normalized, "offen", "offene", "noch nicht verplant", "unverplant"):
            open_statuses = ("Neu", "Offen", "In Planung")
            counts = self._status_counts(TransportOrder)
            total = sum(count for status, count in counts.items() if status.casefold() in {v.casefold() for v in open_statuses})
            details = self._format_status_breakdown(counts, allowed=open_statuses)
            text = f"Aktuell {self._verb(total)} {total} offene Transportaufträge vorhanden."
            if details:
                text += f" Davon: {details}."
            return DirectAnswer(text)
        return None

    def _answer_resource_availability(self, normalized: str) -> DirectAnswer | None:
        if self._contains_any(normalized, *self._ANALYSIS_WORDS):
            return None
        asks_free = self._contains_any(normalized, "frei", "freie", "verfügbar", "verfügbare kapaz")
        if not asks_free:
            return None

        if self._contains_any(normalized, "fahrzeug", "fahrzeuge", "lkw", "zugmaschine"):
            count = self._count_available(Vehicle, Vehicle.active, Vehicle.status)
            return DirectAnswer(self._count_sentence(count, "Fahrzeug", "Fahrzeuge", "frei bzw. verfügbar"))

        if self._contains_any(normalized, "trailer", "auflieger"):
            count = self._count_available(Trailer, Trailer.active, Trailer.status)
            return DirectAnswer(self._count_sentence(count, "Trailer", "Trailer", "frei bzw. verfügbar"))

        # Fahrer besitzen derzeit kein belastbares Statusfeld. Bei einer unspezifischen
        # Frage wird deshalb nicht geraten, sondern die KI darf gezielt nachfragen.
        return None

    def _open_tours_answer(self) -> str:
        counts = self._status_counts(Tour)
        open_counts = {
            status: count
            for status, count in counts.items()
            if status.casefold() not in self._CLOSED_TOUR_STATUSES
        }
        total = sum(open_counts.values())
        details = self._format_status_breakdown(open_counts)
        text = f"Aktuell {self._verb(total)} {total} offene Touren vorhanden."
        if details:
            text += f" Davon: {details}."
        text += " Abgeschlossene, erledigte und stornierte Touren wurden nicht als offen gezählt."
        return text

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.casefold().strip())

    @staticmethod
    def _contains_any(value: str, *terms: str) -> bool:
        return any(term in value for term in terms)

    @staticmethod
    def _verb(count: int) -> str:
        return "ist" if count == 1 else "sind"

    @classmethod
    def _count_sentence(cls, count: int, singular: str, plural: str, suffix: str) -> str:
        label = singular if count == 1 else plural
        return f"Aktuell {cls._verb(count)} {count} {label} {suffix}."

    def _tour_is_open_condition(self):
        return func.lower(Tour.status).notin_(tuple(self._CLOSED_TOUR_STATUSES))

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.session.scalar(statement) or 0)

    def _count_status(self, model, status: str) -> int:
        return self._count(model, func.lower(model.status) == status.casefold())

    def _status_counts(self, model) -> dict[str, int]:
        statement = select(model.status, func.count()).group_by(model.status)
        return {str(status or "Ohne Status"): int(count) for status, count in self.session.execute(statement)}

    @staticmethod
    def _format_status_breakdown(counts: dict[str, int], allowed: tuple[str, ...] | None = None) -> str:
        allowed_folded = {item.casefold() for item in allowed} if allowed else None
        items = [
            (status, count)
            for status, count in counts.items()
            if count and (allowed_folded is None or status.casefold() in allowed_folded)
        ]
        items.sort(key=lambda item: (item[0].casefold(), item[1]))
        return ", ".join(f"{count} „{status}“" for status, count in items)

    def _count_available(self, model, active_column, status_column) -> int:
        statuses = tuple(self._AVAILABLE_RESOURCE_STATUSES)
        return self._count(model, active_column.is_(True), func.lower(status_column).in_(statuses))

    def _active_and_total(self, model, active_column) -> tuple[int, int]:
        total = self._count(model)
        active = self._count(model, active_column.is_(True))
        return active, total

    @staticmethod
    def _format_active_total(label: str, active: int, total: int) -> str:
        if active == total:
            return f"In LeipzigerFlow sind aktuell {total} aktive {label} gespeichert."
        inactive = total - active
        return (
            f"In LeipzigerFlow sind aktuell {active} aktive {label} gespeichert. "
            f"Zusätzlich sind {inactive} inaktive Datensätze vorhanden ({total} insgesamt)."
        )
