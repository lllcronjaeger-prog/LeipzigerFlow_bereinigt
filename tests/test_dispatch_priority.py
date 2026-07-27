from datetime import date
from types import SimpleNamespace

from leipzigerflow.planner.engine.priority import OrderPriorityEngine


def _order(priority):
    return SimpleNamespace(
        id=1,
        order_number="A-1",
        loading_date=date(2026, 7, 23),
        loading_time_until=None,
        unloading_time_until=None,
        status="Neu",
        required_trailer_type="Plane",
        dispatch_priority=priority,
    )


def test_own_fleet_priority_is_ranked_before_sale_preferred():
    engine = OrderPriorityEngine()
    own = engine.build(_order("Eigenfuhrpark bevorzugt"), date(2026, 7, 23))
    sale = engine.build(_order("Verkauf bevorzugt"), date(2026, 7, 23))
    assert own.priority_score > sale.priority_score
    assert own.priority_score - sale.priority_score >= 1000


def test_sale_preferred_remains_plannable_after_priority_orders():
    engine = OrderPriorityEngine()
    sale = engine.build(_order("Verkauf bevorzugt"), date(2026, 7, 23))
    assert sale.priority_score >= 0
    assert any("Verkauf bevorzugt" in reason for reason in sale.priority_reasons)


def test_sale_distance_threshold_rule_is_validated():
    from leipzigerflow.planner.engine.rules import DispatchRules

    rules = DispatchRules(sale_distance_threshold_km=0)
    try:
        rules.validate()
    except ValueError as exc:
        assert "sale_distance_threshold_km" in str(exc)
    else:
        raise AssertionError("Expected invalid sale distance threshold to raise")


def test_longhaul_sale_order_is_reserved_for_subcontractor():
    from datetime import datetime, time
    from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
    from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState, VehicleClass
    from leipzigerflow.routing.models import RouteResult

    loading = SimpleNamespace(id=1, full_display="Germersheim", opening_hours="00:00-23:59", loading_duration_minutes=60)
    unloading = SimpleNamespace(id=2, full_display="Koblenz", opening_hours="00:00-23:59", unloading_duration_minutes=60)
    order = SimpleNamespace(
        id=10, order_number="SALE-130", loading_date=date(2026, 7, 27), loading_time_from=time(8), loading_time_until=time(18),
        unloading_date=date(2026, 7, 28), unloading_time_from=time(8), unloading_time_until=time(18),
        loading_location=loading, unloading_location=unloading, loading_location_id=1, unloading_location_id=2,
        status="Neu", remarks="", required_trailer_type="Plane", dispatch_priority="Verkauf bevorzugt",
        route_distance_km=217.0,
    )
    resource = ResourceAvailability(
        vehicle_id=1, vehicle_label="KA-LL 1", driver_id=1, driver_label="Fahrer",
        available_at=datetime(2026, 7, 27, 6), location_id=1, location_label="Germersheim",
        state=ResourceState.FREE, vehicle_class=VehicleClass.STANDARD, trailer_type="Plane",
        duty_start_at=datetime(2026, 7, 27, 6), duty_end_at=datetime(2026, 7, 27, 16),
    )
    result = AutomaticDispatcher().simulate([resource], [order], date(2026, 7, 27))
    assert result.assigned_count == 0
    assert result.subcontractor_count == 1
    assert any("Subunternehmer" in reason for reason in result.unassigned[0].reasons)
