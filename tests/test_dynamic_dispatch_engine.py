from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine import (
    AutomaticDispatcher,
    DecisionHistoryStore,
    DispatchOptimizer,
    DispatchRules,
    DynamicDispatchEngine,
    OptimizationProfile,
    PlanningEvent,
    PlanningEventManager,
    PlanningEventType,
    ResourceAvailability,
    ResourceManager,
    ResourceState,
    VehicleClass,
)


def _location(location_id: int, name: str):
    return SimpleNamespace(
        id=location_id,
        name=name,
        full_display=name,
        opening_hours="06:00-18:00",
        loading_duration_minutes=60,
        unloading_duration_minutes=60,
    )


def _order(order_id: int):
    loading = _location(1, "Ladestelle")
    unloading = _location(2, "Entladestelle")
    return SimpleNamespace(
        id=order_id,
        order_number=f"LF-{order_id}",
        loading_date=date(2026, 7, 21),
        loading_time_from=time(8, 0),
        loading_time_until=time(12, 0),
        unloading_date=date(2026, 7, 21),
        unloading_time_from=None,
        unloading_time_until=None,
        loading_location=loading,
        unloading_location=unloading,
        loading_location_id=1,
        unloading_location_id=2,
        status="Neu",
        remarks="",
        required_trailer_type="Plane",
    )


def _resource(vehicle_id: int):
    return ResourceAvailability(
        vehicle_id=vehicle_id,
        vehicle_label=f"L-LL {vehicle_id}",
        driver_id=vehicle_id,
        driver_label=f"Fahrer {vehicle_id}",
        available_at=datetime(2026, 7, 21, 6, 0),
        location_id=1,
        location_label="Ladestelle",
        state=ResourceState.FREE,
        vehicle_class=VehicleClass.STANDARD,
        trailer_type="Plane",
    )


def test_event_manager_limits_replanning_to_affected_order():
    event = PlanningEvent(PlanningEventType.NEW_ORDER, datetime.now(), entity_id=12)
    scope = PlanningEventManager().determine_scope([event])
    assert scope.order_ids == frozenset({12})
    assert not scope.full_replanning


def test_dynamic_engine_only_replans_affected_order():
    event = PlanningEvent(PlanningEventType.NEW_ORDER, datetime.now(), entity_id=2)
    result = DynamicDispatchEngine().replan(
        [_resource(1)], [_order(1), _order(2)], date(2026, 7, 21), [event]
    )
    assert result.orders_total == 1
    assert result.assignments[0].order_id == 2
    assert "Neuer Auftrag" in result.replanning_reasons


def test_resource_manager_applies_delay_without_stored_driver_availability():
    manager = ResourceManager([_resource(1)])
    manager.apply_delay(1, 45)
    assert manager.all()[0].available_at == datetime(2026, 7, 21, 6, 45)


def test_optimizer_stability_threshold():
    optimizer = DispatchOptimizer(DispatchRules(stability_threshold_points=12))
    assert not optimizer.should_replace_existing(80, 90)
    assert optimizer.should_replace_existing(80, 92)


def test_dispatcher_adds_confidence_and_history(tmp_path):
    history = DecisionHistoryStore(tmp_path / "history.jsonl")
    result = AutomaticDispatcher(history_store=history).simulate(
        [_resource(1), _resource(2)], [_order(1)], date(2026, 7, 21),
        profile=OptimizationProfile.FAST,
    )
    assert result.assignments[0].confidence_percent >= 0
    assert result.assignments[0].confidence_label in {"Sehr hoch", "Hoch", "Mittel", "Niedrig"}
    assert result.optimization_profile == "Schnellplanung"
    entries = history.read()
    assert len(entries) == 1
    assert entries[0].order_number == "LF-1"
