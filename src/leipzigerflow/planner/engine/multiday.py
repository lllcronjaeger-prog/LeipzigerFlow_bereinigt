from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta

from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState


@dataclass(slots=True)
class VehicleDayState:
    vehicle_id: int
    vehicle_label: str
    planning_day: date
    location_id: int | None
    location_label: str
    available_at: datetime
    trailer_id: int | None = None
    trailer_label: str = ""
    trailer_loaded: bool = False
    return_to_base_required: bool = False
    home_base_location_id: int | None = None
    home_base_location_label: str = ""


@dataclass(slots=True)
class MultiDayPlanningResult:
    start_day: date
    horizon_days: int
    daily_results: dict[date, object] = field(default_factory=dict)
    end_states: dict[date, list[VehicleDayState]] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)

    @property
    def assigned_count(self) -> int:
        return sum(getattr(result, "assigned_count", 0) for result in self.daily_results.values())

    @property
    def open_count(self) -> int:
        return sum(getattr(result, "open_count", 0) for result in self.daily_results.values())


class FutureDemandIndex:
    """Compact look-ahead index used only as a soft score.

    Hard rules remain authoritative. A future bonus can only choose between
    already feasible candidates.
    """

    def __init__(self, orders_by_day: dict[date, list]):
        self._loading_counts: dict[date, Counter[int]] = {}
        for planning_day, orders in orders_by_day.items():
            counts: Counter[int] = Counter()
            for order in orders:
                location_id = getattr(order, "loading_location_id", None)
                if location_id is not None:
                    counts[int(location_id)] += 1
            self._loading_counts[planning_day] = counts

    def score_for_destination(
        self,
        unloading_location_id: int | None,
        planning_day: date,
        *,
        max_lookahead_days: int = 3,
    ) -> tuple[int, list[str]]:
        if unloading_location_id is None:
            return 0, []
        total = 0
        reasons: list[str] = []
        for offset in range(1, max(1, max_lookahead_days) + 1):
            target_day = planning_day + timedelta(days=offset)
            count = self._loading_counts.get(target_day, Counter()).get(int(unloading_location_id), 0)
            if not count:
                continue
            # The nearer the demand, the stronger the bonus. The cap prevents
            # look-ahead from dominating today's operational score.
            points_per_order = max(4, 16 - (offset - 1) * 5)
            bonus = min(48, count * points_per_order)
            total += bonus
            reasons.append(
                f"Zukunftspositionierung: {count} Folgeauftrag/Folgeaufträge am {target_day:%d.%m.%Y} +{bonus}"
            )
        return min(80, total), reasons


class MultiDayStateProjector:
    """Projects the explicit day-end resource state into the next workday."""

    DEFAULT_START = time(8, 0)

    def project_day_end(self, resources, result, planning_day: date) -> list[VehicleDayState]:
        assignments_by_vehicle: dict[int, list] = {}
        for assignment in getattr(result, "assignments", []) or []:
            assignments_by_vehicle.setdefault(int(assignment.vehicle_id), []).append(assignment)

        projected: list[VehicleDayState] = []
        for resource in resources:
            vehicle_id = int(resource.vehicle_id)
            assignments = sorted(
                assignments_by_vehicle.get(vehicle_id, []),
                key=lambda item: item.available_again_at,
            )
            last = assignments[-1] if assignments else None
            if last is None:
                location_id = resource.location_id
                location_label = resource.location_label
                available_at = resource.available_at
            elif resource.return_to_base_required:
                location_id = resource.home_base_location_id
                location_label = resource.home_base_location_label or "Heimatbasis"
                available_at = last.available_again_at + timedelta(minutes=max(0, int(last.return_to_base_minutes or 0)))
            else:
                location_id = getattr(last, "unloading_location_id", None)
                if location_id is None:
                    # ProposedAssignment stores labels but not the unloading id;
                    # the dispatcher adds it dynamically for projection.
                    location_id = getattr(last, "projected_end_location_id", None)
                location_label = last.unloading_location_label or resource.location_label
                available_at = last.available_again_at
            projected.append(VehicleDayState(
                vehicle_id=vehicle_id,
                vehicle_label=resource.vehicle_label,
                planning_day=planning_day,
                location_id=location_id,
                location_label=location_label,
                available_at=available_at,
                trailer_id=resource.trailer_id,
                trailer_label=resource.trailer_label,
                trailer_loaded=resource.trailer_loaded,
                return_to_base_required=resource.return_to_base_required,
                home_base_location_id=resource.home_base_location_id,
                home_base_location_label=resource.home_base_location_label,
            ))
        return projected

    def resources_for_next_day(
        self,
        resources,
        states: list[VehicleDayState],
        next_day: date,
    ) -> list[ResourceAvailability]:
        state_by_vehicle = {state.vehicle_id: state for state in states}
        next_resources: list[ResourceAvailability] = []
        for resource in resources:
            state = state_by_vehicle.get(int(resource.vehicle_id))
            if state is None:
                continue
            start_at = datetime.combine(next_day, self.DEFAULT_START)
            # A previous day's work never consumes the new day's duty budget.
            next_resources.append(replace(
                resource,
                available_at=start_at,
                duty_start_at=start_at,
                duty_end_at=start_at + timedelta(hours=10),
                location_id=state.location_id,
                location_label=state.location_label,
                state=ResourceState.FREE,
                source_tour_id=None,
                source_tour_number="",
            ))
        return next_resources
