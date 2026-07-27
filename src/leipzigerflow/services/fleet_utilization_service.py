from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle, VehicleOwnership
from leipzigerflow.planner.time_planning import TimePlanningEngine


@dataclass(slots=True)
class VehicleUtilizationRow:
    vehicle_id: int
    vehicle_label: str
    ownership_type: str
    vehicle_class: str
    tour_count: int
    order_count: int
    planned_minutes: int
    capacity_minutes: int
    free_minutes: int
    utilization_percent: float

    @property
    def capacity_hint(self) -> str:
        if self.free_minutes < 120:
            return "Praktisch ausgelastet"
        if self.free_minutes < 300:
            return "Eine kurze regionale Tour möglich"
        if self.free_minutes < 540:
            return "Eine zusätzliche Tour kann eingekauft werden"
        return "Eine große oder mehrere kurze Touren können eingekauft werden"


@dataclass(slots=True)
class FleetUtilizationSnapshot:
    date_from: date
    date_to: date
    vehicles: list[VehicleUtilizationRow]

    @property
    def own_tours(self) -> int:
        return sum(row.tour_count for row in self.vehicles if row.ownership_type == VehicleOwnership.OWN.value)

    @property
    def foreign_tours(self) -> int:
        return sum(row.tour_count for row in self.vehicles if row.ownership_type == VehicleOwnership.FOREIGN.value)

    @property
    def total_tours(self) -> int:
        return self.own_tours + self.foreign_tours

    @property
    def own_orders(self) -> int:
        return sum(row.order_count for row in self.vehicles if row.ownership_type == VehicleOwnership.OWN.value)

    @property
    def foreign_orders(self) -> int:
        return sum(row.order_count for row in self.vehicles if row.ownership_type == VehicleOwnership.FOREIGN.value)

    @property
    def average_utilization(self) -> float:
        values = [row.utilization_percent for row in self.vehicles if row.capacity_minutes > 0]
        return mean(values) if values else 0.0

    @property
    def additional_tour_capacity(self) -> int:
        # Konservative betriebliche Schätzung: eine zusätzliche Tour je angefangene 5 freie Stunden.
        return sum(row.free_minutes // 300 for row in self.vehicles)


class FleetUtilizationService:
    """Ermittelt Touranzahl und zeitliche Auslastung der eigenen und fremden Fahrzeuge."""

    DEFAULT_SHIFT_MINUTES = 10 * 60

    def __init__(self, session: Session):
        self.session = session
        self.time_engine = TimePlanningEngine()

    def build(self, date_from: date, date_to: date) -> FleetUtilizationSnapshot:
        if date_to < date_from:
            date_from, date_to = date_to, date_from

        vehicles = list(
            self.session.scalars(
                select(Vehicle)
                .options(joinedload(Vehicle.staffing_profile))
                .where(Vehicle.active.is_(True))
                .order_by(Vehicle.vehicle_number, Vehicle.license_plate)
            ).unique()
        )
        tours = list(
            self.session.scalars(
                select(Tour)
                .options(
                    joinedload(Tour.vehicle),
                    selectinload(Tour.positions)
                    .joinedload(TourPosition.transport_order)
                    .joinedload(TransportOrder.loading_location),
                    selectinload(Tour.positions)
                    .joinedload(TourPosition.transport_order)
                    .joinedload(TransportOrder.unloading_location),
                )
                .where(Tour.tour_date >= date_from, Tour.tour_date <= date_to)
                .order_by(Tour.tour_date, Tour.planned_start_time, Tour.tour_number)
            ).unique()
        )

        day_count = (date_to - date_from).days + 1
        rows: list[VehicleUtilizationRow] = []
        for vehicle in vehicles:
            vehicle_tours = [tour for tour in tours if tour.vehicle_id == vehicle.id and tour.status != "Storniert"]
            planned_minutes = 0
            for tour in vehicle_tours:
                if not tour.positions:
                    continue
                schedule = self.time_engine.build_schedule(tour)
                planned_minutes += max(0, round((schedule.end_at - schedule.start_at).total_seconds() / 60))

            profile = getattr(vehicle, "staffing_profile", None)
            daily_capacity = self.DEFAULT_SHIFT_MINUTES
            if profile is not None:
                daily_capacity = max(60, int(profile.shift_minutes or self.DEFAULT_SHIFT_MINUTES))
                if profile.sequential_double_shift and profile.relief_driver_id:
                    daily_capacity *= 2
            capacity_minutes = daily_capacity * day_count
            free_minutes = max(0, capacity_minutes - planned_minutes)
            utilization = min(100.0, planned_minutes / capacity_minutes * 100.0) if capacity_minutes else 0.0
            rows.append(
                VehicleUtilizationRow(
                    vehicle_id=int(vehicle.id),
                    vehicle_label=vehicle.display_name,
                    ownership_type=getattr(vehicle, "ownership_type", VehicleOwnership.OWN.value),
                    vehicle_class=vehicle.vehicle_class,
                    tour_count=len(vehicle_tours),
                    order_count=sum(len(tour.positions) for tour in vehicle_tours),
                    planned_minutes=planned_minutes,
                    capacity_minutes=capacity_minutes,
                    free_minutes=free_minutes,
                    utilization_percent=utilization,
                )
            )

        return FleetUtilizationSnapshot(date_from=date_from, date_to=date_to, vehicles=rows)
