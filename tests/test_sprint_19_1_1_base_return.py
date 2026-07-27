from datetime import date, time
from types import SimpleNamespace

from leipzigerflow.planner.time_planning import TimePlanningEngine


class RouteProvider:
    def route(self, origin_location_id: int, destination_location_id: int):
        pair = (origin_location_id, destination_location_id)
        durations = {
            (1, 2): (60.0, 60),
            (2, 3): (40.0, 40),
            (3, 1): (70.0, 70),
        }
        distance, minutes = durations[pair]
        return SimpleNamespace(distance_km=distance, duration_minutes=minutes, estimated=False)


def location(identifier: int, name: str):
    return SimpleNamespace(id=identifier, name=name, full_display=name, loading_duration_minutes=0, unloading_duration_minutes=0)


def tour(operation_type: str, *, relief: bool = False):
    base = location(1, "Basis Ettlingen")
    loading = location(2, "Karlsruhe")
    unloading = location(3, "Germersheim")
    order = SimpleNamespace(
        id=11,
        order_number="LF-11",
        loading_location=loading,
        unloading_location=unloading,
        loading_date=date(2026, 7, 28),
        unloading_date=date(2026, 7, 28),
        loading_time_from=None,
        loading_time_until=None,
        unloading_time_from=None,
        unloading_time_until=None,
        loading_time_flexible=True,
        unloading_time_flexible=True,
        loading_open_from=None,
        loading_open_until=None,
    )
    profile = SimpleNamespace(
        sequential_double_shift=relief,
        relief_driver_id=2 if relief else None,
    )
    vehicle = SimpleNamespace(
        operation_type=operation_type,
        daily_return_required=operation_type == "Nahverkehr",
        home_base="Ettlingen",
        home_base_location=base,
        staffing_profile=profile,
    )
    return SimpleNamespace(
        id=1,
        tour_date=date(2026, 7, 28),
        planned_start_time=time(6, 0),
        previous_available_at=None,
        previous_location=base,
        driver=None,
        vehicle=vehicle,
        positions=[SimpleNamespace(id=1, position=1, transport_order=order)],
    )


def test_local_tour_contains_visible_return_to_base_and_counts_it():
    schedule = TimePlanningEngine(RouteProvider()).build_schedule(tour("Nahverkehr"))

    assert schedule.travels[-1].origin_name == "Germersheim"
    assert schedule.travels[-1].destination_name == "Basis Ettlingen"
    assert schedule.travels[-1].is_empty_run is True
    assert schedule.stops[-1].kind == "Basisrückkehr"
    assert schedule.total_distance_km == 170.0
    assert schedule.total_driving_minutes > 100


def test_long_haul_tour_does_not_get_daily_base_return():
    schedule = TimePlanningEngine(RouteProvider()).build_schedule(tour("Fernverkehr"))

    assert all(stop.kind != "Basisrückkehr" for stop in schedule.stops)
    assert schedule.total_distance_km == 100.0
    assert schedule.total_driving_minutes < 100


def test_relief_shift_always_returns_to_base():
    candidate = tour("Nahverkehr", relief=True)
    candidate.vehicle.daily_return_required = False
    schedule = TimePlanningEngine(RouteProvider()).build_schedule(candidate)

    assert schedule.stops[-1].kind == "Basisrückkehr"
    assert schedule.travels[-1].destination_name == "Basis Ettlingen"
