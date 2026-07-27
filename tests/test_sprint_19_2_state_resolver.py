from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.availability import ResourceAvailabilityEngine
from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, VehicleClass
from leipzigerflow.routing.models import RouteResult


class RouteProvider:
    def calculate(self, origin_id, destination_id):
        durations = {
            (1, 2): 30,  # Karlsruhe -> Germersheim
            (2, 1): 30,
            (2, 3): 35,  # Germersheim -> Mannheim
            (3, 4): 60,  # Mannheim -> Ettlingen
            (2, 4): 45,  # Germersheim -> Ettlingen
        }
        return RouteResult(50.0, durations.get((origin_id, destination_id), 30), provider="test")


def loc(i, name):
    return SimpleNamespace(
        id=i, name=name, city=name, full_display=name, opening_hours="00:00-23:59",
        loading_duration_minutes=30, unloading_duration_minutes=30,
    )


def order(i, loading, unloading, day, order_type="Shuttle"):
    return SimpleNamespace(
        id=i, order_number=f"O-{i}", order_type=order_type,
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


def test_local_driver_restarts_next_day_at_base_not_last_customer():
    ettlingen = loc(4, "Ettlingen")
    mannheim = loc(3, "Mannheim")
    previous_order = SimpleNamespace(unloading_location=mannheim, loading_location=ettlingen)
    previous_tour = SimpleNamespace(
        id=10, vehicle_id=1, driver_id=7, driver_display="Nah Fahrer",
        tour_number="T-1", tour_date=date(2026, 7, 20), planned_start_time=time(6, 0),
        positions=[SimpleNamespace(transport_order=previous_order)],
    )
    driver = SimpleNamespace(id=7, full_name="Nah Fahrer", allowed_operation="Nahverkehr", home_base="Ettlingen")
    profile = SimpleNamespace(primary_driver=driver, first_shift_start=time(6, 0), shift_minutes=600,
                              sequential_double_shift=False, relief_driver_id=None)
    vehicle = SimpleNamespace(
        id=1, active=True, license_plate="KA-LL 8043", description="", status="",
        operation_type="Fernverkehr", daily_return_required=False, home_base="Ettlingen",
        home_base_location=ettlingen, staffing_profile=profile, trailer=SimpleNamespace(trailer_type="Plane"),
        vehicle_class="Standard", absences=[],
    )
    previous_tour.vehicle = vehicle
    previous_tour.driver = driver

    resource = ResourceAvailabilityEngine().build([vehicle], [previous_tour], date(2026, 7, 21))[0]

    assert resource.location_id == ettlingen.id
    assert resource.available_at == datetime(2026, 7, 21, 6, 0)
    assert resource.return_to_base_required is True


def test_three_shuttles_are_iteratively_densified_with_base_return_reserved():
    day = date(2026, 7, 21)
    karlsruhe, germersheim, ettlingen = loc(1, "Karlsruhe"), loc(2, "Germersheim"), loc(4, "Ettlingen")
    resource = ResourceAvailability(
        vehicle_id=1, vehicle_label="KA-LL 8043", driver_id=7, driver_label="Nah Fahrer",
        available_at=datetime(2026, 7, 21, 6, 0), location_id=ettlingen.id, location_label="Ettlingen",
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD, trailer_type="Plane",
        duty_start_at=datetime(2026, 7, 21, 6, 0), duty_end_at=datetime(2026, 7, 21, 16, 0),
        return_to_base_required=True, home_base_location_id=ettlingen.id,
        home_base_location_label="Ettlingen",
    )
    orders = [order(i, karlsruhe, germersheim, day) for i in range(1, 4)]

    result = AutomaticDispatcher(routing_service=RouteProvider()).simulate([resource], orders, day)

    assert result.assigned_count == 3
    assert result.open_count == 0
    assert any("Rückfahrt zur Basis" in reason for reason in result.assignments[-1].reasons)
