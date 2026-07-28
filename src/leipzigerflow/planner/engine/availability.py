from __future__ import annotations

from datetime import date, datetime, time, timedelta

from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, VehicleClass
from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.planner.engine.vehicle_state_service import VehicleStateService
from leipzigerflow.planner.engine.trailer_state import BaseTrailerPolicy


class ResourceAvailabilityEngine:
    """Leitet Fahrzeug-/Fahrerschichten aus den Touren des Planungstags ab.

    Bei sequentieller Doppelbesetzung entstehen zwei getrennte Ressourcenfenster
    desselben Fahrzeugs. Sie überlappen nicht und sind keine Doppelbesatzung im
    Sinne gleichzeitiger Fahrerbesetzung.
    """

    DEFAULT_SHIFT_MINUTES = 10 * 60

    def __init__(self, time_engine: TimePlanningEngine | None = None):
        self.time_engine = time_engine or TimePlanningEngine()
        self.vehicle_state_service = VehicleStateService()
        self.trailer_policy = BaseTrailerPolicy()

    def build(self, vehicles, tours, planning_day: date) -> list[ResourceAvailability]:
        relevant = [tour for tour in tours if tour.vehicle_id]
        by_vehicle: dict[int, list] = {}
        for tour in relevant:
            by_vehicle.setdefault(int(tour.vehicle_id), []).append(tour)

        known_locations = self._known_locations(tours)
        resources: list[ResourceAvailability] = []
        for vehicle in vehicles:
            if not getattr(vehicle, "active", True):
                continue
            vehicle_tours = sorted(by_vehicle.get(int(vehicle.id), []), key=self._tour_sort_key)
            today_tours = [tour for tour in vehicle_tours if tour.tour_date == planning_day]
            if today_tours:
                resources.extend(self._from_day_tours(vehicle, today_tours, planning_day, known_locations))
            else:
                last_tour = vehicle_tours[-1] if vehicle_tours else None
                resources.append(self._from_vehicle(vehicle, last_tour, planning_day, known_locations))
        return resources

    def _from_day_tours(self, vehicle, tours, planning_day: date, known_locations=()) -> list[ResourceAvailability]:
        result: list[ResourceAvailability] = []
        for index, tour in enumerate(tours, start=1):
            schedule = self.time_engine.build_schedule(tour)
            shift_start = datetime.combine(planning_day, tour.planned_start_time or time(6, 0))
            profile = getattr(vehicle, "staffing_profile", None)
            shift_minutes = int(getattr(profile, "shift_minutes", self.DEFAULT_SHIFT_MINUTES) or self.DEFAULT_SHIFT_MINUTES)
            shift_end = shift_start + timedelta(minutes=shift_minutes)
            driver = getattr(tour, "driver", None)
            resolved = self.vehicle_state_service.resolve_day_start(vehicle, driver, planning_day, shift_start, tour, known_locations)
            last_position = tour.positions[-1] if tour.positions else None
            location = resolved.home_base_location if resolved.return_to_base_required else (last_position.transport_order.unloading_location if last_position else resolved.start_location)
            available_at = max(shift_start, schedule.end_at)
            state = self._state_for_tour(tour, schedule.end_at, planning_day)
            blocked_reason = self._blocking_reason(vehicle, schedule.start_at, schedule.end_at, tour)
            if blocked_reason:
                state = ResourceState.WORKSHOP
            result.append(ResourceAvailability(
                vehicle_id=int(vehicle.id),
                vehicle_label=self._vehicle_label(vehicle),
                driver_id=int(tour.driver_id) if tour.driver_id else None,
                driver_label=tour.driver_display or "nicht zugeordnet",
                available_at=available_at,
                location_id=int(location.id) if location is not None else None,
                location_label=(getattr(location, "full_display", "") or getattr(location, "name", "") or "Standort unbekannt"),
                state=state,
                vehicle_class=self._vehicle_class(vehicle),
                trailer_type=self._trailer_type(vehicle, tour),
                **self._trailer_state_fields(vehicle, tour),
                source_tour_id=int(tour.id),
                source_tour_number=str(tour.tour_number),
                reason=blocked_reason or f"Schicht {index}: {shift_start:%H:%M} bis {shift_end:%H:%M}.",
                duty_start_at=shift_start,
                duty_end_at=shift_end,
                shift_label=f"Schicht {index}",
                return_to_base_required=resolved.return_to_base_required,
                home_base_location_id=(int(resolved.home_base_location.id) if resolved.home_base_location is not None else None),
                home_base_location_label=resolved.home_base_label,
                operation_type=str(getattr(vehicle, "operation_type", "") or ""),
                driver_operation=str(getattr(driver, "allowed_operation", "") or ""),
            ))
        return result

    def _from_vehicle(self, vehicle, last_tour, planning_day: date, known_locations=()) -> ResourceAvailability:
        profile = getattr(vehicle, "staffing_profile", None)
        start_time = getattr(profile, "first_shift_start", None) or time(6, 0)
        shift_minutes = int(getattr(profile, "shift_minutes", self.DEFAULT_SHIFT_MINUTES) or self.DEFAULT_SHIFT_MINUTES)
        duty_start = datetime.combine(planning_day, start_time)
        duty_end = duty_start + timedelta(minutes=shift_minutes)
        status = str(getattr(vehicle, "status", "") or "").casefold()
        state = ResourceState.WORKSHOP if "werkstatt" in status else ResourceState.DEFECT if "defekt" in status else ResourceState.FREE
        blocked_reason = self._blocking_reason(vehicle, duty_start, duty_end, None)
        if blocked_reason:
            state = ResourceState.WORKSHOP
        driver = getattr(profile, "primary_driver", None)
        driver_id = int(driver.id) if driver is not None else None
        driver_label = getattr(driver, "full_name", "") or "nicht zugeordnet"
        resolved = self.vehicle_state_service.resolve_day_start(vehicle, driver, planning_day, duty_start, last_tour, known_locations)
        if last_tour is None or last_tour.tour_date < planning_day:
            return ResourceAvailability(
                vehicle_id=int(vehicle.id), vehicle_label=self._vehicle_label(vehicle),
                driver_id=driver_id, driver_label=driver_label,
                available_at=resolved.start_at,
                location_id=(int(resolved.start_location.id) if resolved.start_location is not None else None),
                location_label=(getattr(resolved.start_location, "full_display", "") or getattr(resolved.start_location, "name", "") or resolved.home_base_label or "Standort unbekannt"),
                state=state, vehicle_class=self._vehicle_class(vehicle),
                trailer_type=self._trailer_type(vehicle, None),
                **self._trailer_state_fields(vehicle, None),
                reason=blocked_reason or resolved.reason,
                duty_start_at=duty_start, duty_end_at=duty_end, shift_label="Schicht 1",
                return_to_base_required=resolved.return_to_base_required,
                home_base_location_id=(int(resolved.home_base_location.id) if resolved.home_base_location is not None else None),
                home_base_location_label=resolved.home_base_label,
                operation_type=str(getattr(vehicle, "operation_type", "") or ""),
                driver_operation=str(getattr(driver, "allowed_operation", "") or ""),
            )

        schedule = self.time_engine.build_schedule(last_tour)
        # On a new planning day local resources restart at the base, independent
        # of the last customer shown on the previous day's operative positions.
        location = resolved.start_location
        return ResourceAvailability(
            vehicle_id=int(vehicle.id), vehicle_label=self._vehicle_label(vehicle),
            driver_id=int(last_tour.driver_id) if last_tour.driver_id else driver_id,
            driver_label=last_tour.driver_display or driver_label,
            available_at=resolved.start_at if resolved.return_to_base_required else max(duty_start, schedule.end_at),
            location_id=int(location.id) if location is not None else None,
            location_label=getattr(location, "full_display", "") or getattr(location, "name", "") or "Standort unbekannt",
            state=(ResourceState.WORKSHOP if self._blocking_reason(vehicle, schedule.start_at, schedule.end_at, last_tour) else self._state_for_tour(last_tour, schedule.end_at, planning_day)),
            vehicle_class=self._vehicle_class(vehicle), trailer_type=self._trailer_type(vehicle, last_tour),
            **self._trailer_state_fields(vehicle, last_tour),
            source_tour_id=int(last_tour.id), source_tour_number=str(last_tour.tour_number),
            reason=self._blocking_reason(vehicle, schedule.start_at, schedule.end_at, last_tour) or resolved.reason,
            duty_start_at=duty_start, duty_end_at=duty_end, shift_label="Schicht 1",
            return_to_base_required=resolved.return_to_base_required,
            home_base_location_id=(int(resolved.home_base_location.id) if resolved.home_base_location is not None else None),
            home_base_location_label=resolved.home_base_label,
            operation_type=str(getattr(vehicle, "operation_type", "") or ""),
            driver_operation=str(getattr(driver, "allowed_operation", "") or ""),
        )


    @staticmethod
    def _known_locations(tours):
        unique = {}
        for tour in tours:
            for position in getattr(tour, "positions", ()):
                order = getattr(position, "transport_order", None)
                for location in (getattr(order, "loading_location", None), getattr(order, "unloading_location", None)):
                    if location is not None:
                        unique[getattr(location, "id", id(location))] = location
        return tuple(unique.values())

    @staticmethod
    def _returns_to_base(vehicle) -> bool:
        operation_type = str(getattr(vehicle, "operation_type", "") or "").casefold()
        profile = getattr(vehicle, "staffing_profile", None)
        return bool(
            operation_type == "nahverkehr"
            or getattr(vehicle, "daily_return_required", False)
            or (
                profile
                and getattr(profile, "sequential_double_shift", False)
                and getattr(profile, "relief_driver_id", None)
            )
        )


    @staticmethod
    def _blocking_reason(vehicle, starts_at: datetime, ends_at: datetime, tour=None) -> str:
        resources = [("Fahrzeug", getattr(vehicle, "absences", ()))]
        trailer = getattr(tour, "trailer", None) if tour is not None else None
        trailer = trailer or getattr(vehicle, "trailer", None)
        if trailer is not None:
            resources.append(("Trailer", getattr(trailer, "absences", ())))
        for label, absences in resources:
            for absence in absences:
                if not getattr(absence, "active", True):
                    continue
                absence_start = getattr(absence, "starts_at", None)
                absence_end = getattr(absence, "ends_at", None)
                if absence_start and absence_end and absence_start < ends_at and starts_at < absence_end:
                    return f"{label} gesperrt: {getattr(absence, 'reason', 'Sperrzeit')} bis {absence_end:%d.%m.%Y %H:%M}."
        return ""

    def _trailer_state_fields(self, vehicle, tour) -> dict:
        trailer = getattr(tour, "trailer", None) if tour is not None else None
        trailer = trailer or getattr(vehicle, "trailer", None)
        state = self.trailer_policy.resolve(vehicle, trailer)
        return {
            "trailer_id": state.trailer_id,
            "trailer_label": state.trailer_label,
            "trailer_location_kind": state.location_kind.value,
            "trailer_location_label": state.location_label,
            "trailer_loaded": state.loaded,
        }

    @staticmethod
    def _trailer_type(vehicle, tour) -> str:
        trailer = getattr(tour, "trailer", None) if tour is not None else None
        trailer = trailer or getattr(vehicle, "trailer", None)
        return str(getattr(trailer, "trailer_type", "") or "")

    @staticmethod
    def _tour_sort_key(tour):
        return tour.tour_date, getattr(tour, "planned_start_time", None) or time(6, 0), int(tour.id or 0)

    @staticmethod
    def _vehicle_label(vehicle) -> str:
        plate = str(getattr(vehicle, "license_plate", "") or "").strip()
        description = str(getattr(vehicle, "description", "") or "").strip()
        return " – ".join(value for value in (plate, description) if value)

    @staticmethod
    def _vehicle_class(vehicle) -> VehicleClass:
        vehicle_type = str(getattr(vehicle, "vehicle_class", "Standard") or "Standard").casefold()
        trailer_type = str(getattr(getattr(vehicle, "trailer", None), "trailer_type", "") or "").casefold()
        return VehicleClass.MEGA if vehicle_type == "mega" and "mega" in trailer_type else VehicleClass.STANDARD

    @staticmethod
    def _state_for_tour(tour, end_at: datetime, planning_day: date) -> ResourceState:
        status = str(getattr(tour, "status", "") or "").casefold()
        if status in {"abgeschlossen", "erledigt"} or end_at.date() < planning_day:
            return ResourceState.FREE
        if "werkstatt" in status:
            return ResourceState.WORKSHOP
        if "defekt" in status:
            return ResourceState.DEFECT
        return ResourceState.ON_TOUR
