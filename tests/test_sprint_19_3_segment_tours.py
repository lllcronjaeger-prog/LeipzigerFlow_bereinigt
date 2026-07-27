from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, TourSegmentType, VehicleClass
from leipzigerflow.planner.engine.state_resolver import ResourceStateResolver
from leipzigerflow.routing.models import RouteResult


class RouteProvider:
    def calculate(self, origin_id, destination_id):
        routes = {
            (4, 1): (55.0, 45),
            (1, 2): (30.0, 30),
            (2, 1): (30.0, 30),
            (2, 4): (50.0, 45),
        }
        km, minutes = routes.get((origin_id, destination_id), (20.0, 30))
        return RouteResult(km, minutes, provider="test", estimated=False)


def loc(identifier, name):
    return SimpleNamespace(
        id=identifier, name=name, city=name, full_display=name,
        opening_hours="00:00-23:59", loading_duration_minutes=30,
        unloading_duration_minutes=30,
    )


def make_order(identifier, loading, unloading, day):
    return SimpleNamespace(
        id=identifier, order_number=f"O-{identifier}", order_type="Shuttle",
        loading_date=day, unloading_date=day,
        loading_time_from=None, loading_time_until=None,
        unloading_time_from=None, unloading_time_until=None,
        loading_time_flexible=True, unloading_time_flexible=True,
        loading_open_from=time(0, 0), loading_open_until=time(23, 59),
        unloading_open_from=time(0, 0), unloading_open_until=time(23, 59),
        loading_location=loading, unloading_location=unloading,
        loading_location_id=loading.id, unloading_location_id=unloading.id,
        required_trailer_type="Plane", status="Neu", remarks="",
        customer=SimpleNamespace(disposition_priority=5, own_fleet_preferred=False),
        dispatch_priority="Eigenfuhrpark bevorzugt",
    )


def test_monday_friday_longhaul_driver_starts_at_base_after_weekend_without_daily_return():
    base = loc(4, "Ettlingen")
    driver = SimpleNamespace(work_model="Montag-Freitag", allowed_operation="", home_base="Ettlingen")
    vehicle = SimpleNamespace(
        operation_type="Fernverkehr", daily_return_required=False,
        home_base="Ettlingen", home_base_location=base, staffing_profile=None,
    )
    last = SimpleNamespace(positions=[SimpleNamespace(transport_order=SimpleNamespace(unloading_location=loc(3, "Mannheim")))])
    state = ResourceStateResolver().resolve(vehicle, driver, date(2026, 7, 27), datetime(2026, 7, 27, 6), last)
    assert state.return_to_base_required is False
    assert state.start_location is base
    assert "Wochenend" in state.reason


def test_proposed_tour_contains_visible_start_and_return_empty_runs():
    day = date(2026, 7, 27)
    base, loading, unloading = loc(4, "Ettlingen"), loc(1, "Karlsruhe"), loc(2, "Germersheim")
    resource = ResourceAvailability(
        vehicle_id=1, vehicle_label="KA-LL 8043", driver_id=7, driver_label="Fahrer 1",
        available_at=datetime(2026, 7, 27, 6), location_id=base.id, location_label=base.full_display,
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD, trailer_type="Plane",
        duty_start_at=datetime(2026, 7, 27, 6), duty_end_at=datetime(2026, 7, 27, 16),
        return_to_base_required=True, home_base_location_id=base.id, home_base_location_label=base.full_display,
    )
    result = AutomaticDispatcher(routing_service=RouteProvider()).simulate(
        [resource], [make_order(1, loading, unloading, day)], day
    )
    tour = result.proposed_tours[0]
    assert [segment.segment_type for segment in tour.segments] == [
        TourSegmentType.START_EMPTY_RUN,
        TourSegmentType.TRANSPORT,
        TourSegmentType.RETURN_TO_BASE,
    ]
    assert tour.segments[0].origin_label == "Ettlingen"
    assert tour.segments[-1].destination_label == "Ettlingen"
    assert tour.planned_start_at < tour.assignments[0].loading_at
    assert tour.planned_end_at > tour.assignments[-1].available_again_at
