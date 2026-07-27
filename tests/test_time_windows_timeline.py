from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.planner.timeline import build_timeline_entries


class Router:
    def route(self, origin_location_id, destination_location_id):
        minutes = 60 if {origin_location_id, destination_location_id} == {1, 2} else 90
        return SimpleNamespace(distance_km=float(minutes), duration_minutes=minutes, estimated=False)


def location(identifier, name, opening_hours=""):
    return SimpleNamespace(
        id=identifier,
        name=name,
        opening_hours=opening_hours,
        loading_duration_minutes=60,
        unloading_duration_minutes=60,
    )


def order(identifier, loading, unloading):
    return SimpleNamespace(
        id=identifier,
        order_number=f"A-{identifier}",
        loading_location=loading,
        unloading_location=unloading,
        loading_date=date(2026, 7, 25),
        loading_time_from=time(6, 30),
        loading_time_until=time(6, 30),
        loading_time_flexible=True,
        loading_open_from=time(6, 0),
        loading_open_until=time(12, 0),
        unloading_date=date(2026, 7, 27),
        unloading_time_from=time(6, 0),
        unloading_time_until=time(12, 0),
        unloading_time_flexible=True,
        unloading_open_from=time(6, 0),
        unloading_open_until=time(12, 0),
    )


def tour_for(order_obj, previous_location=None, previous_available_at=None):
    position = SimpleNamespace(id=1, position=1, transport_order=order_obj)
    return SimpleNamespace(
        id=1,
        tour_date=date(2026, 7, 25),
        planned_start_time=time(6, 0),
        positions=[position],
        driver=None,
        previous_location=previous_location,
        previous_available_at=previous_available_at,
    )


def test_pe008_calendar_days_are_inclusive():
    koblenz = location(2, "Koblenz", "06:00-12:00")
    ettlingen = location(3, "Ettlingen", "06:00-12:00")
    schedule = TimePlanningEngine(Router()).build_schedule(tour_for(order(1, koblenz, ettlingen)))
    assert schedule.deployment_days == 3
    assert schedule.overnight_count == 2


def test_pe009_previous_tour_creates_visible_empty_run():
    woellstein = location(1, "Wöllstein")
    koblenz = location(2, "Koblenz", "06:00-12:00")
    ettlingen = location(3, "Ettlingen", "06:00-12:00")
    schedule = TimePlanningEngine(Router()).build_schedule(
        tour_for(order(1, koblenz, ettlingen), woellstein, datetime(2026, 7, 25, 7, 0))
    )
    assert schedule.travels[0].is_empty_run is True
    assert schedule.travels[0].origin_name == "Wöllstein"
    assert schedule.travels[0].destination_name == "Koblenz"
    assert any(item.kind == "empty_run" for item in build_timeline_entries(schedule))


def test_pe010_flexible_booking_moves_to_actual_arrival_inside_opening_hours():
    woellstein = location(1, "Wöllstein")
    koblenz = location(2, "Koblenz", "06:00-12:00")
    ettlingen = location(3, "Ettlingen", "06:00-12:00")
    schedule = TimePlanningEngine(Router()).build_schedule(
        tour_for(order(1, koblenz, ettlingen), woellstein, datetime(2026, 7, 25, 7, 0))
    )
    loading = next(stop for stop in schedule.stops if stop.kind == "Laden")
    assert loading.planned_arrival == datetime(2026, 7, 25, 7, 56)
    assert loading.conflict == ""


def test_pe011_flexible_window_is_rejected_only_after_opening_end():
    woellstein = location(1, "Wöllstein")
    koblenz = location(2, "Koblenz", "06:00-12:00")
    ettlingen = location(3, "Ettlingen", "06:00-12:00")
    schedule = TimePlanningEngine(Router()).build_schedule(
        tour_for(order(1, koblenz, ettlingen), woellstein, datetime(2026, 7, 25, 12, 0))
    )
    loading = next(stop for stop in schedule.stops if stop.kind == "Laden")
    assert loading.planned_arrival == datetime(2026, 7, 25, 12, 56)
    assert "überschritten" in loading.conflict
