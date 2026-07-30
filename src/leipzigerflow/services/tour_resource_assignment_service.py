from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_driver_assignment import TourDriverAssignment
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.vehicle_resource_assignment import VehicleResourceAssignment
from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.services.rotation_manager import RotationManager


class ResourceAssignmentError(ValueError):
    pass


class TourResourceAssignmentService:
    """Ressourcenpflege für Touren und zeitlich gültige Fahrzeugbesetzungen."""

    def __init__(self, session: Session):
        self.session = session
        self.rotation = RotationManager()
        self.time_planning = TimePlanningEngine()

    def active_drivers(self) -> list[Driver]:
        return list(self.session.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name, Driver.first_name)))

    def active_trailers(self) -> list[Trailer]:
        return list(self.session.scalars(select(Trailer).where(Trailer.active.is_(True)).order_by(Trailer.trailer_number)))

    def assignment_for_vehicle(self, vehicle_id: int, day: date) -> VehicleResourceAssignment | None:
        return self.session.scalar(
            select(VehicleResourceAssignment)
            .where(
                VehicleResourceAssignment.vehicle_id == int(vehicle_id),
                VehicleResourceAssignment.active.is_(True),
                VehicleResourceAssignment.valid_from <= day,
                or_(VehicleResourceAssignment.valid_until.is_(None), VehicleResourceAssignment.valid_until >= day),
            )
            .order_by(VehicleResourceAssignment.valid_from.desc(), VehicleResourceAssignment.id.desc())
        )

    def apply_vehicle_assignment_to_tour(self, tour: Tour, *, overwrite: bool = False) -> bool:
        """Übernimmt die am Tourtag gültige Stammbesetzung in eine konkrete Tour."""
        if not tour.vehicle_id:
            return False
        assignment = self.assignment_for_vehicle(tour.vehicle_id, tour.tour_date)
        if assignment is None:
            return False
        changed = False
        if assignment.driver_id and (overwrite or not tour.driver_id):
            driver = self.session.get(Driver, assignment.driver_id)
            if driver and self.rotation.status(driver, tour.tour_date).available:
                schedule = self.time_planning.build_schedule(tour)
                tour.driver_id = driver.id
                tour.driver_assignments.clear()
                tour.driver_assignments.append(TourDriverAssignment(
                    driver_id=driver.id,
                    starts_at=schedule.start_at,
                    ends_at=schedule.end_at,
                    sequence=1,
                ))
                changed = True
        if assignment.trailer_id and (overwrite or not tour.trailer_id):
            tour.trailer_id = assignment.trailer_id
            changed = True
        return changed

    def assign_driver_segments(
        self,
        tour: Tour,
        segments: list[dict],
        *,
        propagate_last: bool = False,
        valid_until: date | None = None,
        until_changed: bool = False,
        commit: bool = True,
    ) -> None:
        if not segments:
            raise ResourceAssignmentError("Mindestens ein Fahrerabschnitt ist erforderlich.")
        vehicle = getattr(tour, "vehicle", None)
        if vehicle is None:
            raise ResourceAssignmentError("Vor einem Fahrerwechsel muss ein Fahrzeug zugeordnet sein.")
        base_location_id = getattr(vehicle, "home_base_location_id", None)
        base_name = str(getattr(vehicle, "home_base", "") or "").strip()
        if len(segments) > 1 and not (base_location_id or base_name):
            raise ResourceAssignmentError("Am Fahrzeug ist keine Basis hinterlegt. Ein Fahrerwechsel ist daher nicht möglich.")

        normalized = sorted(segments, key=lambda item: item["starts_at"])
        for index, item in enumerate(normalized):
            if item["ends_at"] <= item["starts_at"]:
                raise ResourceAssignmentError("Jeder Fahrerabschnitt benötigt ein Ende nach dem Beginn.")
            if index and normalized[index - 1]["ends_at"] != item["starts_at"]:
                raise ResourceAssignmentError("Fahrerabschnitte müssen lückenlos aneinander anschließen.")
            driver = self.session.get(Driver, int(item["driver_id"]))
            if driver is None:
                raise ResourceAssignmentError("Ein ausgewählter Fahrer wurde nicht gefunden.")
            if not self.rotation.status(driver, item["starts_at"].date()).available:
                raise ResourceAssignmentError(
                    f"{driver.full_name or driver.match_code} ist am {item['starts_at']:%d.%m.%Y} laut Arbeitsmodell nicht im Einsatz."
                )

        tour.driver_assignments.clear()
        for index, item in enumerate(normalized, start=1):
            tour.driver_assignments.append(TourDriverAssignment(
                driver_id=int(item["driver_id"]), starts_at=item["starts_at"], ends_at=item["ends_at"],
                sequence=index,
                change_base_location_id=base_location_id if index > 1 else None,
                change_base_name=base_name if index > 1 else "",
                change_reason=str(item.get("reason", "") or ""),
            ))
        tour.driver_id = int(normalized[0]["driver_id"])

        if propagate_last:
            last_driver_id = int(normalized[-1]["driver_id"])
            self._store_vehicle_assignment(
                tour,
                driver_id=last_driver_id,
                trailer_id=tour.trailer_id or getattr(vehicle, "trailer_id", None),
                valid_from=tour.tour_date + timedelta(days=1),
                valid_until=None if until_changed else valid_until,
                reason="Manuelle Fahrerübernahme aus Plantafel",
            )
            self._propagate_existing_tours(
                tour,
                driver_id=last_driver_id,
                trailer_id=None,
                valid_from=tour.tour_date + timedelta(days=1),
                valid_until=None if until_changed else valid_until,
            )
        if commit:
            self.session.commit()

    def assign_single_driver(
        self,
        tour: Tour,
        driver_id: int,
        start_at: datetime,
        end_at: datetime,
        *,
        propagate: bool = False,
        valid_until: date | None = None,
        until_changed: bool = False,
    ) -> None:
        self.assign_driver_segments(
            tour,
            [{"driver_id": driver_id, "starts_at": start_at, "ends_at": end_at, "reason": ""}],
            propagate_last=propagate,
            valid_until=valid_until,
            until_changed=until_changed,
        )

    def assign_trailer(
        self,
        tour: Tour,
        trailer_id: int,
        *,
        propagate: bool = True,
        valid_until: date | None = None,
        until_changed: bool = True,
    ) -> None:
        trailer = self.session.get(Trailer, int(trailer_id))
        if trailer is None:
            raise ResourceAssignmentError("Der Trailer wurde nicht gefunden.")
        tour.trailer_id = trailer.id
        vehicle = getattr(tour, "vehicle", None)
        if vehicle is not None:
            vehicle.trailer_id = trailer.id
        if propagate and tour.vehicle_id:
            self._store_vehicle_assignment(
                tour,
                driver_id=tour.driver_id,
                trailer_id=trailer.id,
                valid_from=tour.tour_date,
                valid_until=None if until_changed else valid_until,
                reason="Manuelle Trailerübernahme aus Plantafel",
            )
            self._propagate_existing_tours(
                tour,
                driver_id=None,
                trailer_id=trailer.id,
                valid_from=tour.tour_date,
                valid_until=None if until_changed else valid_until,
            )
        self.session.commit()

    def _store_vehicle_assignment(
        self,
        tour: Tour,
        *,
        driver_id: int | None,
        trailer_id: int | None,
        valid_from: date,
        valid_until: date | None,
        reason: str,
    ) -> VehicleResourceAssignment:
        if not tour.vehicle_id:
            raise ResourceAssignmentError("Für eine dauerhafte Übernahme muss ein Fahrzeug zugeordnet sein.")
        if valid_until is not None and valid_until < valid_from:
            raise ResourceAssignmentError("Das Gültigkeitsende liegt vor dem Gültigkeitsbeginn.")

        # Eine offene ältere Zuordnung endet am Vortag der neuen Zuordnung.
        previous = self.session.scalar(
            select(VehicleResourceAssignment)
            .where(
                VehicleResourceAssignment.vehicle_id == tour.vehicle_id,
                VehicleResourceAssignment.active.is_(True),
                VehicleResourceAssignment.valid_from < valid_from,
                or_(VehicleResourceAssignment.valid_until.is_(None), VehicleResourceAssignment.valid_until >= valid_from),
            )
            .order_by(VehicleResourceAssignment.valid_from.desc())
        )
        if previous is not None:
            previous.valid_until = valid_from - timedelta(days=1)

        current = self.session.scalar(
            select(VehicleResourceAssignment).where(
                VehicleResourceAssignment.vehicle_id == tour.vehicle_id,
                VehicleResourceAssignment.valid_from == valid_from,
            )
        )
        vehicle = tour.vehicle
        if current is None:
            current = VehicleResourceAssignment(vehicle_id=tour.vehicle_id, valid_from=valid_from)
            self.session.add(current)
        if driver_id is not None:
            current.driver_id = driver_id
        if trailer_id is not None:
            current.trailer_id = trailer_id
        current.valid_until = valid_until
        current.base_location_id = getattr(vehicle, "home_base_location_id", None)
        current.base_name = str(getattr(vehicle, "home_base", "") or "")
        current.reason = reason
        current.active = True
        self.session.flush()
        return current

    def _propagate_existing_tours(
        self,
        source_tour: Tour,
        *,
        driver_id: int | None,
        trailer_id: int | None,
        valid_from: date,
        valid_until: date | None,
    ) -> None:
        if not source_tour.vehicle_id:
            return
        conditions = [Tour.vehicle_id == source_tour.vehicle_id, Tour.tour_date >= valid_from]
        if valid_until is not None:
            conditions.append(Tour.tour_date <= valid_until)
        future = list(self.session.scalars(select(Tour).where(*conditions).order_by(Tour.tour_date, Tour.id)))
        for item in future:
            if driver_id is not None:
                driver = self.session.get(Driver, driver_id)
                if driver is None or not self.rotation.status(driver, item.tour_date).available:
                    continue
                schedule = self.time_planning.build_schedule(item)
                item.driver_id = driver_id
                item.driver_assignments.clear()
                item.driver_assignments.append(TourDriverAssignment(
                    driver_id=driver_id,
                    starts_at=schedule.start_at,
                    ends_at=schedule.end_at,
                    sequence=1,
                ))
            if trailer_id is not None:
                item.trailer_id = trailer_id
