from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_driver_assignment import TourDriverAssignment
from leipzigerflow.models.vehicle import Vehicle, VehicleOperationType
from leipzigerflow.services.tour_service import TourService


class DailyTourService:
    """Legt an Werktagen automatisch die Grundtouren der einsatzfähigen Flotte an."""

    BLOCKED_STATUS_PARTS = ("defekt", "werkstatt", "stillgelegt", "außer betrieb")

    def __init__(self, session):
        self.session = session

    def ensure_for_day(self, planning_day: date) -> int:
        if planning_day.weekday() >= 5:
            return 0
        vehicles = list(self.session.scalars(
            select(Vehicle).options(
                joinedload(Vehicle.trailer),
                joinedload(Vehicle.staffing_profile),
            ).where(Vehicle.active.is_(True))
        ).unique())
        existing = list(self.session.scalars(select(Tour).where(Tour.tour_date == planning_day)))
        existing_by_vehicle = {int(t.vehicle_id): t for t in existing if t.vehicle_id}
        tour_service = TourService(self.session)
        created = 0

        for vehicle in vehicles:
            if any(part in str(vehicle.status or "").casefold() for part in self.BLOCKED_STATUS_PARTS):
                continue
            profile = vehicle.staffing_profile
            start_time = getattr(profile, "first_shift_start", None)
            if start_time is None:
                from datetime import time
                start_time = time(6, 0)

            tour = existing_by_vehicle.get(int(vehicle.id))
            if tour is None:
                tour = tour_service.create({
                    "tour_date": planning_day,
                    "planned_start_time": start_time,
                    "status": "Geplant",
                    "driver_id": getattr(profile, "primary_driver_id", None),
                    "vehicle_id": vehicle.id,
                    "remarks": "Automatisch angelegte Tagestour",
                })
                tour.trailer_id = vehicle.trailer_id
                existing_by_vehicle[int(vehicle.id)] = tour
                created += 1

            # Wechselfahrer sind Fahrerabschnitte derselben Fahrzeugtour. Es wird
            # ausdrücklich keine zweite Tour/Folgeschicht mehr erzeugt.
            if profile and getattr(profile, "primary_driver_id", None):
                tour.driver_id = profile.primary_driver_id
                if not list(getattr(tour, "driver_assignments", []) or []):
                    shift_minutes = max(1, int(profile.shift_minutes or 600))
                    first_start = datetime.combine(planning_day, start_time)
                    first_end = first_start + timedelta(minutes=shift_minutes)
                    tour.driver_assignments.append(TourDriverAssignment(
                        driver_id=profile.primary_driver_id,
                        starts_at=first_start,
                        ends_at=first_end,
                        sequence=1,
                    ))
                    if (
                        vehicle.operation_type == VehicleOperationType.LOCAL.value
                        and profile.sequential_double_shift
                        and profile.relief_driver_id
                    ):
                        tour.driver_assignments.append(TourDriverAssignment(
                            driver_id=profile.relief_driver_id,
                            starts_at=first_end,
                            ends_at=first_end + timedelta(minutes=shift_minutes),
                            sequence=2,
                            change_base_location_id=vehicle.home_base_location_id,
                            change_base_name=str(vehicle.home_base or ""),
                            change_reason="Planmäßiger Fahrerwechsel laut Fahrzeugbesetzung",
                        ))

        self.session.commit()
        return created
