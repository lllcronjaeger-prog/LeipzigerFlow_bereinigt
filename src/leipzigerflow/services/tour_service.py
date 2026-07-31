from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from leipzigerflow.database.repositories.tour_repository import TourRepository
from leipzigerflow.models.location import Location
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_driver_assignment import TourDriverAssignment
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder


class TourValidationError(ValueError):
    pass


class TourService:
    STATUSES = (
        "Geplant",
        "Unterwegs",
        "Abgeschlossen",
        "Storniert",
    )
    ARCHIVE_STATUSES = frozenset({"Abgeschlossen", "Erledigt"})

    def __init__(self, session: Session):
        self._session = session
        self.repository = TourRepository(session)

    def get_all(self) -> list[Tour]:
        return self.repository.get_all()

    def get_for_period(self, start: date, end: date) -> list[Tour]:
        return self.repository.get_for_period(start, end)

    def get_previous_for_vehicles(self, vehicle_ids: set[int], before: date) -> dict[int, Tour]:
        return self.repository.get_previous_for_vehicles(vehicle_ids, before)


    def consolidate_duplicate_vehicle_tours(self) -> int:
        """Führt legacybedingte Doppeltouren je Fahrzeug und Tag zusammen.

        Fahrerwechsel erzeugen niemals eine zweite Tour. Aufträge und
        Fahrerabschnitte werden in die älteste Tour übernommen.
        """
        tours = [tour for tour in self.repository.get_all() if tour.vehicle_id]
        groups: dict[tuple[date, int], list[Tour]] = {}
        for tour in tours:
            groups.setdefault((tour.tour_date, int(tour.vehicle_id)), []).append(tour)
        merged = 0
        for group in groups.values():
            if len(group) < 2:
                continue
            group.sort(key=lambda item: (item.created_at, item.id))
            primary = group[0]
            existing_order_ids = {int(p.transport_order_id) for p in primary.positions}
            next_position = max((int(p.position) for p in primary.positions), default=0)
            assignments = list(primary.driver_assignments)
            for duplicate in group[1:]:
                for position in list(duplicate.positions):
                    if int(position.transport_order_id) in existing_order_ids:
                        duplicate.positions.remove(position)
                        continue
                    next_position += 1
                    position.tour = primary
                    position.position = next_position
                    existing_order_ids.add(int(position.transport_order_id))
                duplicate_assignments = list(duplicate.driver_assignments)
                assignments.extend(duplicate_assignments)
                if not duplicate_assignments and duplicate.driver_id:
                    # Legacy-Folgeschichten hatten nur driver_id und eine zweite
                    # Tour. Beim Zusammenführen wird daraus ein Fahrerabschnitt
                    # innerhalb der einen Fahrzeugtour.
                    profile = getattr(getattr(primary, "vehicle", None), "staffing_profile", None)
                    shift_minutes = max(1, int(getattr(profile, "shift_minutes", 600) or 600))
                    starts_at = datetime.combine(
                        duplicate.tour_date,
                        duplicate.planned_start_time or datetime.min.time(),
                    )
                    assignments.append(TourDriverAssignment(
                        driver_id=duplicate.driver_id,
                        starts_at=starts_at,
                        ends_at=starts_at + timedelta(minutes=shift_minutes),
                        sequence=len(assignments) + 1,
                        change_base_location_id=getattr(getattr(primary, "vehicle", None), "home_base_location_id", None),
                        change_base_name=str(getattr(getattr(primary, "vehicle", None), "home_base", "") or ""),
                        change_reason="Übernahme aus ehemaliger Folgeschicht",
                    ))
                if not primary.driver_id and duplicate.driver_id:
                    primary.driver_id = duplicate.driver_id
                if not primary.trailer_id and duplicate.trailer_id:
                    primary.trailer_id = duplicate.trailer_id
                self._session.delete(duplicate)
                merged += 1
            if assignments:
                unique = {}
                for item in assignments:
                    key = (item.driver_id, item.starts_at, item.ends_at)
                    unique[key] = item
                primary.driver_assignments.clear()
                for sequence, item in enumerate(sorted(unique.values(), key=lambda value: value.starts_at), start=1):
                    primary.driver_assignments.append(type(item)(
                        driver_id=item.driver_id,
                        starts_at=item.starts_at,
                        ends_at=item.ends_at,
                        change_base_location_id=item.change_base_location_id,
                        change_base_name=item.change_base_name,
                        change_reason=item.change_reason,
                        sequence=sequence,
                    ))
        if merged:
            self._session.commit()
        return merged

    def synchronize_completed_tours(self, start: date | None = None, end: date | None = None) -> int:
        """Schließt Touren automatisch ab, sobald alle enthaltenen Aufträge erledigt sind.

        Leere und stornierte Touren werden bewusst nicht verändert. Die Methode
        ist idempotent und kann gefahrlos vor jeder Aktualisierung der Ansichten
        aufgerufen werden.
        """
        changed = 0
        tours = self.repository.get_for_period(start, end) if start is not None and end is not None else self.repository.get_all()
        for tour in tours:
            if tour.status == "Storniert" or not tour.positions:
                continue
            orders = [position.transport_order for position in tour.positions]
            if all(order.status == "Erledigt" for order in orders):
                if tour.status not in self.ARCHIVE_STATUSES:
                    tour.status = "Abgeschlossen"
                    self._session.add(tour)
                    changed += 1
        if changed:
            self._session.commit()
        return changed

    @classmethod
    def is_archived(cls, tour: Tour) -> bool:
        return str(tour.status) in cls.ARCHIVE_STATUSES

    def get(self, tour_id: int) -> Tour | None:
        return self.repository.get(tour_id)

    def search(self, search_text: str = "", status: str = "") -> list[Tour]:
        return self.repository.search(search_text=search_text, status=status)

    def get_unassigned_orders(self) -> list[TransportOrder]:
        return self.repository.get_unassigned_orders()

    def get_unassigned_orders_for_day(self, planning_day: date) -> list[TransportOrder]:
        return self.repository.get_unassigned_orders_for_day(planning_day)

    def create(self, data: dict[str, Any]) -> Tour:
        cleaned = self._validate_and_clean(data)
        cleaned["tour_number"] = self._next_tour_number()
        return self.repository.add(Tour(**cleaned))

    def update(self, tour: Tour, data: dict[str, Any]) -> Tour:
        cleaned = self._validate_and_clean(data)
        previous_status = tour.status
        for field_name, value in cleaned.items():
            setattr(tour, field_name, value)
        self._apply_order_statuses(tour, previous_status=previous_status)
        return self.repository.update(tour)

    def change_status(self, tour: Tour, status: str) -> Tour:
        if status not in self.STATUSES:
            raise TourValidationError("Der Tourstatus ist ungültig.")
        previous_status = tour.status
        tour.status = status
        self._apply_order_statuses(tour, previous_status=previous_status)
        return self.repository.update(tour)


    def set_planning_locked(self, tour: Tour, locked: bool) -> Tour:
        if tour.status in ("Unterwegs", "Abgeschlossen") and not locked:
            raise TourValidationError(
                "Unterwegs befindliche oder abgeschlossene Touren bleiben geschützt."
            )
        tour.planning_locked = bool(locked)
        return self.repository.update(tour)

    def set_many_planning_locked(self, tours: list[Tour], locked: bool) -> int:
        changed = 0
        for tour in tours:
            self.set_planning_locked(tour, locked)
            changed += 1
        return changed

    def add_order(self, tour: Tour, order: TransportOrder) -> Tour:
        return self.add_order_at(tour, order, None)

    def add_orders(self, tour: Tour, orders: list[TransportOrder]) -> Tour:
        """Disponiert mehrere offene Aufträge in genau einer Transaktion."""
        self._assert_tour_editable(tour, "Die Tour ist fixiert und kann nicht verändert werden.")
        self._assert_orders_match_tour_date(tour, orders)
        existing_ids = {int(position.transport_order_id) for position in tour.positions}
        additions = [order for order in orders if int(order.id) not in existing_ids]
        if not additions:
            return tour
        for order in additions:
            if order.status in ("Erledigt", "Storniert"):
                raise TourValidationError(
                    "Erledigte oder stornierte Aufträge können nicht disponiert werden."
                )
            if order.assignment_type == "Subunternehmer" or not order.auto_dispatch_eligible:
                raise TourValidationError(
                    "Der Auftrag ist bereits extern vergeben und kann nicht auf den eigenen Fuhrpark disponiert werden."
                )
        ordered = sorted(tour.positions, key=lambda item: (item.position, item.id or 0))
        with self._session.no_autoflush:
            for order in additions:
                position = TourPosition(
                    tour=tour,
                    transport_order=order,
                    position=self._new_temporary_position(),
                )
                self._session.add(position)
                ordered.append(position)
                order.status = self._order_status_for_tour(tour.status)
        return self._commit_position_orders({tour: ordered}, refresh_tour_id=int(tour.id))

    def add_order_at(
        self,
        tour: Tour,
        order: TransportOrder,
        target_index: int | None,
    ) -> Tour:
        self._assert_tour_editable(tour, "Die Tour ist fixiert und kann nicht verändert werden.")
        self._assert_orders_match_tour_date(tour, [order])
        if any(position.transport_order_id == order.id for position in tour.positions):
            return self.reorder_order(tour, order.id, target_index or 0)
        if order.status in ("Erledigt", "Storniert"):
            raise TourValidationError(
                "Erledigte oder stornierte Aufträge können nicht disponiert werden."
            )
        if order.assignment_type == "Subunternehmer" or not order.auto_dispatch_eligible:
            raise TourValidationError(
                "Der Auftrag ist bereits extern vergeben und kann nicht auf den eigenen Fuhrpark disponiert werden."
            )
        ordered = sorted(tour.positions, key=lambda item: (item.position, item.id or 0))
        insert_at = len(ordered) if target_index is None else max(
            0, min(int(target_index), len(ordered))
        )
        with self._session.no_autoflush:
            new_position = TourPosition(
                tour=tour,
                transport_order=order,
                position=self._new_temporary_position(),
            )
            self._session.add(new_position)
            ordered.insert(insert_at, new_position)
            order.status = self._order_status_for_tour(tour.status)
        return self._commit_position_orders({tour: ordered}, refresh_tour_id=int(tour.id))

    def remove_order(self, tour: Tour, order_id: int) -> Tour:
        self.release_orders(tour, [order_id])
        return self.get(int(tour.id)) or tour

    def release_orders(self, tour: Tour, order_ids: list[int]) -> Tour:
        """Setzt Touraufträge atomar zurück auf 'Neu' und nummeriert konfliktfrei."""
        self._assert_tour_editable(tour, "Die Tour ist fixiert und kann nicht verändert werden.")
        requested = {int(value) for value in order_ids}
        ordered_all = sorted(tour.positions, key=lambda item: (item.position, item.id or 0))
        removed = [p for p in ordered_all if int(p.transport_order_id) in requested]
        if not removed:
            raise TourValidationError("Die ausgewählten Aufträge befinden sich nicht in der Quelltour.")
        remaining = [p for p in ordered_all if p not in removed]
        try:
            # Zuerst alle Positionen konfliktfrei zwischenparken. Danach werden
            # die freizugebenden Positionen auch aus der ORM-Beziehung entfernt.
            # Das ist bei expire_on_commit=False entscheidend: Andernfalls bleibt
            # das bereits gelöschte Objekt mit seiner negativen Hilfsposition in
            # tour.positions sichtbar und erscheint in der UI als Geisterauftrag.
            self._stage_positions(ordered_all)
            for position in removed:
                order = position.transport_order
                if order.status not in ("Erledigt", "Storniert"):
                    order.status = "Neu"
                if position in tour.positions:
                    tour.positions.remove(position)

            # delete-orphan entfernt die gelösten TourPosition-Datensätze. Erst
            # anschließend werden die verbleibenden Positionen sauber von 1 an
            # nummeriert und noch vor dem Commit in die Datenbank geschrieben.
            self._session.flush()
            self._assign_final_positions(remaining)
            self._session.flush()
            self._session.commit()

            # Die Beziehung bewusst verwerfen und frisch laden. So erhalten auch
            # bereits geöffnete Dialoge garantiert nur den aktuellen DB-Zustand.
            self._session.expire(tour, ["positions"])
            return self.get(int(tour.id)) or tour
        except Exception:
            self._session.rollback()
            raise

    def move_order(self, tour: Tour, order_id: int, direction: int) -> Tour:
        self._assert_tour_editable(tour, "Die Tour ist fixiert und kann nicht verändert werden.")
        ordered = sorted(tour.positions, key=lambda item: (item.position, item.id or 0))
        current_index = next(
            (index for index, position in enumerate(ordered) if position.transport_order_id == order_id),
            None,
        )
        if current_index is None:
            return tour
        return self.reorder_order(tour, order_id, current_index + direction)

    def reorder_order(self, tour: Tour, order_id: int, target_index: int) -> Tour:
        self._assert_tour_editable(tour, "Die Tour ist fixiert und kann nicht verändert werden.")
        ordered = sorted(tour.positions, key=lambda item: (item.position, item.id or 0))
        current_index = next(
            (index for index, position in enumerate(ordered) if position.transport_order_id == order_id),
            None,
        )
        if current_index is None:
            return tour
        item = ordered.pop(current_index)
        ordered.insert(max(0, min(int(target_index), len(ordered))), item)
        return self._commit_position_orders({tour: ordered}, refresh_tour_id=int(tour.id))

    def transfer_orders(
        self,
        source_tour: Tour,
        target_tour: Tour,
        order_ids: list[int],
    ) -> Tour:
        """Verschiebt Aufträge atomar und ohne zwischenzeitliche UNIQUE-Kollision."""
        if int(source_tour.id) == int(target_tour.id):
            raise TourValidationError("Quell- und Zieltour sind identisch.")
        self._assert_tour_editable(
            source_tour, "Die Quelltour ist fixiert und kann nicht verändert werden."
        )
        self._assert_tour_editable(
            target_tour, "Die Zieltour ist fixiert und kann nicht verändert werden."
        )
        requested = {int(value) for value in order_ids}
        source_all = sorted(source_tour.positions, key=lambda item: (item.position, item.id or 0))
        moved = [p for p in source_all if int(p.transport_order_id) in requested]
        if not moved:
            raise TourValidationError("Die ausgewählten Aufträge befinden sich nicht in der Quelltour.")
        self._assert_orders_match_tour_date(
            target_tour, [position.transport_order for position in moved]
        )
        source_remaining = [p for p in source_all if p not in moved]
        target_existing = sorted(target_tour.positions, key=lambda item: (item.position, item.id or 0))
        try:
            # Phase 1: Alle betroffenen Datensätze erhalten pro ID eindeutige
            # negative Werte. Erst danach wird die tour_id der verschobenen
            # Positionen geändert. So kann (tour_id, position) nie kollidieren.
            self._stage_positions(source_all + target_existing)
            with self._session.no_autoflush:
                for position in moved:
                    position.tour = target_tour
                    position.transport_order.status = self._order_status_for_tour(target_tour.status)
            self._session.flush()
            self._assign_final_positions(source_remaining)
            self._assign_final_positions(target_existing + moved)
            self._session.commit()
            return self.get(int(target_tour.id)) or target_tour
        except Exception:
            self._session.rollback()
            raise

    @staticmethod
    def _assert_orders_match_tour_date(tour: Tour, orders: list[TransportOrder]) -> None:
        mismatches = [
            order for order in orders
            if getattr(order, "loading_date", None) != getattr(tour, "tour_date", None)
        ]
        if not mismatches:
            return
        numbers = ", ".join(str(order.order_number) for order in mismatches[:5])
        suffix = " …" if len(mismatches) > 5 else ""
        raise TourValidationError(
            "Eine Tagestour darf nur Aufträge mit demselben Ladedatum enthalten. "
            f"Tourdatum: {tour.tour_date:%d.%m.%Y}; abweichend: {numbers}{suffix}. "
            "Für ein anderes Ladedatum bitte eine eigene Tagestour verwenden."
        )

    @staticmethod
    def _assert_tour_editable(tour: Tour, message: str) -> None:
        if getattr(tour, "planning_locked", False):
            raise TourValidationError(message)

    def _commit_position_orders(
        self,
        orders_by_tour: dict[Tour, list[TourPosition]],
        refresh_tour_id: int,
    ) -> Tour:
        try:
            affected = [position for positions in orders_by_tour.values() for position in positions]
            self._stage_positions(affected)
            for positions in orders_by_tour.values():
                self._assign_final_positions(positions)
            self._session.commit()
            return self.get(refresh_tour_id) or next(iter(orders_by_tour))
        except Exception:
            self._session.rollback()
            raise

    def _stage_positions(self, positions: list[TourPosition]) -> None:
        """Vergibt garantiert eindeutige temporäre Positionen und flusht sie."""
        seen: set[int] = set()
        for position in positions:
            identity = int(position.id or id(position))
            while identity in seen:
                identity += 1
            seen.add(identity)
            position.position = -1_000_000_000 - identity
            self._session.add(position)
        self._session.flush()

    @staticmethod
    def _assign_final_positions(positions: list[TourPosition]) -> None:
        for index, position in enumerate(positions, start=1):
            position.position = index

    @staticmethod
    def _new_temporary_position() -> int:
        # Neue Objekte haben noch keine Datenbank-ID. Ein stark negativer Wert
        # verhindert Kollisionen mit regulären und früheren temporären Werten.
        from time import time_ns
        return -2_000_000_000 - (time_ns() % 1_000_000_000)

    def delete(self, tour: Tour) -> None:
        for position in list(tour.positions):
            order = position.transport_order
            if order.status not in ("Erledigt", "Storniert"):
                order.status = "Neu"
        self.repository.delete(tour)


    def _next_tour_number(self) -> str:
        year = date.today().year
        prefix = f"T-{year}-"
        existing = self.repository.get_tour_numbers_for_year(year)
        highest = 0
        for value in existing:
            if not value.startswith(prefix):
                continue
            suffix = value[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"{prefix}{highest + 1:05d}"

    def _validate_and_clean(self, data: dict[str, Any]) -> dict[str, Any]:
        tour_date = data.get("tour_date")
        if not isinstance(tour_date, date):
            raise TourValidationError("Bitte ein gültiges Tourdatum eingeben.")

        status = str(data.get("status", "Geplant")).strip()
        if status not in self.STATUSES:
            raise TourValidationError("Der Tourstatus ist ungültig.")

        return {
            "tour_date": tour_date,
            "planned_start_time": data.get("planned_start_time"),
            "status": status,
            "driver_id": self._optional_positive_int(data.get("driver_id")),
            "vehicle_id": self._optional_positive_int(data.get("vehicle_id")),
            "trailer_id": self._optional_positive_int(data.get("trailer_id")),
            "remarks": str(data.get("remarks", "")).strip(),
        }

    def _apply_order_statuses(self, tour: Tour, previous_status: str) -> None:
        del previous_status
        new_order_status = self._order_status_for_tour(tour.status)
        for position in tour.positions:
            order = position.transport_order
            if order.status == "Storniert":
                continue
            if tour.status == "Storniert":
                if order.status != "Erledigt":
                    order.status = "Neu"
                continue
            order.status = new_order_status

    @staticmethod
    def _order_status_for_tour(tour_status: str) -> str:
        mapping = {
            "Geplant": "Geplant",
            "Unterwegs": "Unterwegs",
            "Abgeschlossen": "Erledigt",
            "Storniert": "Neu",
        }
        return mapping[tour_status]

    @staticmethod
    def _normalize_positions(tour: Tour) -> None:
        for index, position in enumerate(
            sorted(tour.positions, key=lambda item: item.position),
            start=1,
        ):
            position.position = index

    @staticmethod
    def _optional_positive_int(value: Any) -> int | None:
        if value in (None, "", 0):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise TourValidationError(
                "Eine Stammdatenauswahl ist ungültig."
            ) from error
        return number if number > 0 else None

    def analyze_multi_stop_tour(self, tour: Tour, route_provider=None):
        """Bewertet ausschließlich den aktuellen, persistierten Tourstand.

        Nach Drag & Drop können Dialoge noch eine ältere SQLAlchemy-Instanz der
        Tour halten. Vor jeder Optimierung werden deshalb Session und
        Beziehungen verworfen und die Tour vollständig neu geladen.
        """
        from leipzigerflow.planner.optimizer import MultiStopTourOptimizer
        from leipzigerflow.routing import get_default_routing_service

        tour_id = int(tour.id)
        self._session.flush()
        self._session.expire_all()
        current_tour = self.get(tour_id)
        if current_tour is None:
            raise TourValidationError("Die Tour wurde zwischenzeitlich gelöscht.")

        provider = route_provider or get_default_routing_service()
        optimizer = MultiStopTourOptimizer(route_provider=provider)
        positions = sorted(
            list(current_tour.positions),
            key=lambda item: (item.position or 0, item.id or 0),
        )
        orders = [self._to_multi_stop_order(position.transport_order) for position in positions]
        return optimizer.optimize(
            orders,
            tour_start=self._tour_start_datetime(current_tour),
            tour_start_location_id=self._resolve_tour_start_location_id(current_tour),
        )

    def apply_optimized_order(self, tour: Tour, order_ids: list[int] | tuple[int, ...]) -> Tour:
        """Wendet einen Vorschlag nur auf den aktuellen Datenbankstand an."""
        tour_id = int(tour.id)
        self._session.expire_all()
        current_tour = self.get(tour_id)
        if current_tour is None:
            raise TourValidationError("Die Tour wurde zwischenzeitlich gelöscht.")

        requested_ids = [int(value) for value in order_ids]
        current_ids = {int(position.transport_order_id) for position in current_tour.positions}
        if set(requested_ids) != current_ids or len(requested_ids) != len(current_ids):
            raise TourValidationError(
                "Die Tour wurde seit der Optimierung verändert. Bitte die Reihenfolge erneut optimieren."
            )
        ordered_by_id = {
            int(position.transport_order_id): position for position in current_tour.positions
        }
        ordered = [ordered_by_id[order_id] for order_id in requested_ids]
        return self.save_position_order(current_tour, ordered)


    def save_position_order(
        self,
        tour: Tour,
        ordered_positions: list[TourPosition],
    ) -> Tour:
        """Speichert eine vollständige Tourreihenfolge konfliktfrei.

        Die Methode ist die öffentliche Service-API für manuelle und
        optimierte Reihenfolgeänderungen. Sie verwendet dieselbe
        transaktionssichere Positionslogik wie Drag & Drop.
        """
        self._assert_tour_editable(
            tour, "Die Tour ist fixiert und kann nicht verändert werden."
        )
        current_ids = {int(position.id) for position in tour.positions if position.id is not None}
        ordered_ids = [int(position.id) for position in ordered_positions if position.id is not None]
        if len(ordered_positions) != len(tour.positions) or set(ordered_ids) != current_ids:
            raise TourValidationError(
                "Die neue Reihenfolge passt nicht mehr zu den Positionen der Tour."
            )
        return self._commit_position_orders(
            {tour: list(ordered_positions)},
            refresh_tour_id=int(tour.id),
        )


    def _resolve_tour_start_location_id(self, tour: Tour) -> int | None:
        """Ordnet den hinterlegten Fahrzeugstandort einem Standortstammsatz zu.

        Die Fahrzeugverwaltung speichert den Standort historisch als Freitext.
        Für die Routenbewertung wird deshalb gegen Kurzname, Name, Ort, PLZ und
        die vollständige Adresse abgeglichen. Ein eindeutiger exakter Treffer
        hat Vorrang; bei mehreren Treffern wird ein in der Tour verwendeter
        Standort bevorzugt.
        """
        vehicle = getattr(tour, "vehicle", None)
        raw_location = str(getattr(vehicle, "location", "") or "").strip()
        if not raw_location:
            return None

        def normalize(value: object) -> str:
            return "".join(character for character in str(value or "").casefold() if character.isalnum())

        needle = normalize(raw_location)
        if not needle:
            return None

        locations = list(
            self._session.scalars(
                select(Location).where(Location.active.is_(True)).order_by(Location.id)
            )
        )
        exact: list[Location] = []
        partial: list[Location] = []
        for location in locations:
            values = (
                location.short_name,
                location.name,
                location.city,
                location.postal_code,
                location.full_address,
            )
            normalized_values = [normalize(value) for value in values if value]
            if needle in normalized_values:
                exact.append(location)
            elif any(needle in value or value in needle for value in normalized_values if value):
                partial.append(location)

        candidates = exact or partial
        if not candidates:
            return None
        if len(candidates) == 1:
            return int(candidates[0].id)

        used_location_ids = {
            int(location_id)
            for position in tour.positions
            for location_id in (
                position.transport_order.loading_location_id,
                position.transport_order.unloading_location_id,
            )
            if location_id is not None
        }
        used_candidates = [item for item in candidates if int(item.id) in used_location_ids]
        if len(used_candidates) == 1:
            return int(used_candidates[0].id)
        return int(candidates[0].id)

    @staticmethod
    def _tour_start_datetime(tour: Tour):
        from datetime import datetime, time

        return datetime.combine(
            tour.tour_date,
            tour.planned_start_time or time(6, 0),
        )

    @staticmethod
    def _to_multi_stop_order(order: TransportOrder):
        from datetime import datetime, time

        from leipzigerflow.planner.optimizer import MultiStopOrder

        loading_start = datetime.combine(
            order.loading_date,
            order.loading_time_from or time(0, 0),
        )
        loading_end = datetime.combine(
            order.loading_date,
            order.loading_time_until or time(23, 59),
        )
        unloading_start = datetime.combine(
            order.unloading_date,
            order.unloading_time_from or time(0, 0),
        )
        unloading_end = datetime.combine(
            order.unloading_date,
            order.unloading_time_until or time(23, 59),
        )
        loading_duration = getattr(order.loading_location, "loading_duration_minutes", 60) or 60
        unloading_duration = getattr(order.unloading_location, "unloading_duration_minutes", 60) or 60
        return MultiStopOrder(
            order_id=order.id,
            order_number=order.order_number,
            loading_location_id=order.loading_location_id,
            unloading_location_id=order.unloading_location_id,
            loading_window_start=loading_start,
            loading_window_end=loading_end,
            unloading_window_start=unloading_start,
            unloading_window_end=unloading_end,
            loading_duration_minutes=int(loading_duration),
            unloading_duration_minutes=int(unloading_duration),
        )
