from datetime import date, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.transport_chains import TransportChainDetector


def _order(order_id, loading, unloading, day=23, load_hour=6, unload_hour=8):
    return SimpleNamespace(
        id=order_id,
        loading_location_id=loading,
        unloading_location_id=unloading,
        loading_date=date(2026, 7, day),
        unloading_date=date(2026, 7, day),
        loading_time_from=time(load_hour, 0),
        loading_time_until=time(load_hour, 30),
        unloading_time_from=time(unload_hour, 0),
        unloading_time_until=time(unload_hour, 30),
    )


def test_detector_builds_arbitrarily_long_chain():
    orders = [
        _order(1, 10, 20, load_hour=6, unload_hour=7),
        _order(2, 20, 30, load_hour=8, unload_hour=9),
        _order(3, 30, 40, load_hour=10, unload_hour=11),
        _order(4, 40, 50, load_hour=12, unload_hour=13),
        _order(5, 50, 60, load_hour=14, unload_hour=15),
    ]
    plan = TransportChainDetector().build(orders)
    assert plan.roots() == [1]
    assert plan.chain_ids_from(1) == [1, 2, 3, 4, 5]
    assert plan.chain_length_from(1) == 5


def test_round_trip_is_recognized_without_cyclic_graph():
    orders = [
        _order(1, 10, 20, load_hour=6, unload_hour=7),
        _order(2, 20, 30, load_hour=8, unload_hour=9),
        _order(3, 30, 10, load_hour=10, unload_hour=11),
    ]
    plan = TransportChainDetector().build(orders)
    assert plan.chain_ids_from(1) == [1, 2, 3]
    assert plan.is_round_trip(1, {item.id: item for item in orders}) is True
    assert plan.successor(3) is None
