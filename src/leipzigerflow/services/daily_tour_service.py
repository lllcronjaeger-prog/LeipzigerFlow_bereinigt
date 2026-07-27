from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from leipzigerflow.models.tour import Tour
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
        existing_keys = {(int(t.vehicle_id), t.planned_start_time) for t in existing if t.vehicle_id}
        tour_service = TourService(self.session)
        created = 0
        for vehicle in vehicles:
            if any(part in str(vehicle.status or "").casefold() for part in self.BLOCKED_STATUS_PARTS):
                continue
            profile = vehicle.staffing_profile
            start = getattr(profile, "first_shift_start", None)
            if start is None:
                from datetime import time
                start = time(6, 0)
            first_driver_id = getattr(profile, "primary_driver_id", None)
            if (int(vehicle.id), start) not in existing_keys:
                tour = tour_service.create({
                    "tour_date": planning_day,
                    "planned_start_time": start,
                    "status": "Geplant",
                    "driver_id": first_driver_id,
                    "vehicle_id": vehicle.id,
                    "remarks": "Automatisch angelegte Tagestour",
                })
                tour.trailer_id = vehicle.trailer_id
                self.session.commit()
                created += 1
            if (
                profile
                and vehicle.operation_type == VehicleOperationType.LOCAL.value
                and profile.sequential_double_shift
                and profile.relief_driver_id
            ):
                shift_minutes = int(profile.shift_minutes or 600)
                second_start = (datetime.combine(planning_day, start) + timedelta(minutes=shift_minutes)).time()
                if (int(vehicle.id), second_start) not in existing_keys:
                    tour = tour_service.create({
                        "tour_date": planning_day,
                        "planned_start_time": second_start,
                        "status": "Geplant",
                        "driver_id": profile.relief_driver_id,
                        "vehicle_id": vehicle.id,
                        "remarks": "Automatisch angelegte Folgeschicht – keine gleichzeitige Doppelbesatzung",
                    })
                    tour.trailer_id = vehicle.trailer_id
                    self.session.commit()
                    created += 1
        return created
