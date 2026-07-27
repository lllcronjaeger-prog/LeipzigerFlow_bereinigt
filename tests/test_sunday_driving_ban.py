from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.time_planning import TimePlanningEngine


class RouteProvider:
    def route(self, origin_location_id, destination_location_id):
        return SimpleNamespace(distance_km=None, duration_minutes=180, estimated=False)


def _location(identifier, name):
    return SimpleNamespace(
        id=identifier,
        name=name,
        loading_duration_minutes=0,
        unloading_duration_minutes=0,
        opening_hours="",
    )


def test_travel_started_on_sunday_is_delayed_until_monday():
    origin = _location(1, "Start")
    destination = _location(2, "Ziel")
    order = SimpleNamespace(
        id=1,
        order_number="LF-1",
        loading_location=origin,
        unloading_location=destination,
        loading_date=date(2026, 7, 26),  # Sunday
        unloading_date=date(2026, 7, 27),
        loading_time_from=time(0, 0),
        loading_time_until=None,
        unloading_time_from=None,
        unloading_time_until=None,
        loading_time_flexible=False,
        unloading_time_flexible=False,
        loading_open_from=None,
        loading_open_until=None,
        unloading_open_from=None,
        unloading_open_until=None,
    )
    tour = SimpleNamespace(
        id=1,
        tour_date=date(2026, 7, 26),
        planned_start_time=time(0, 0),
        previous_available_at=None,
        previous_location=None,
        driver=None,
        positions=[SimpleNamespace(position=1, id=1, transport_order=order)],
    )

    schedule = TimePlanningEngine(RouteProvider()).build_schedule(tour)

    assert schedule.travels
    assert all(travel.started_at.weekday() != 6 for travel in schedule.travels)
    assert schedule.travels[0].started_at == datetime(2026, 7, 27, 1, 0)
    assert any("Sonntagsfahrverbot" in item.reason for item in schedule.breaks)
