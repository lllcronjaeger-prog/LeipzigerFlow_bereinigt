from datetime import datetime

from leipzigerflow.planner.optimizer import (
    MatrixRouteProvider,
    MultiStopOrder,
    MultiStopTourOptimizer,
)


def _order(
    order_id: int,
    number: str,
    loading_location: int,
    unloading_location: int,
    loading_from: str,
    loading_until: str,
    unloading_from: str,
    unloading_until: str,
) -> MultiStopOrder:
    parse = datetime.fromisoformat
    return MultiStopOrder(
        order_id=order_id,
        order_number=number,
        loading_location_id=loading_location,
        unloading_location_id=unloading_location,
        loading_window_start=parse(loading_from),
        loading_window_end=parse(loading_until),
        unloading_window_start=parse(unloading_from),
        unloading_window_end=parse(unloading_until),
        loading_duration_minutes=30,
        unloading_duration_minutes=30,
    )


def test_optimizer_finds_better_sequence_and_preserves_time_windows():
    provider = MatrixRouteProvider(
        {
            (1, 2): (50.0, 60),
            (3, 4): (50.0, 60),
            (5, 6): (50.0, 60),
            (2, 5): (10.0, 15),
            (6, 3): (10.0, 15),
            (2, 3): (100.0, 120),
            (4, 5): (100.0, 120),
        }
    )
    a = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T08:00", "2026-07-22T07:00", "2026-07-22T10:00")
    b = _order(2, "B", 3, 4, "2026-07-22T12:00", "2026-07-22T15:00", "2026-07-22T13:00", "2026-07-22T18:00")
    c = _order(3, "C", 5, 6, "2026-07-22T09:00", "2026-07-22T11:00", "2026-07-22T10:00", "2026-07-22T13:00")

    result = MultiStopTourOptimizer(provider).optimize(
        [a, b, c], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert result.current.order_ids == (1, 2, 3)
    assert result.optimized.order_ids == (1, 3, 2)
    assert result.optimized.feasible
    assert result.optimized.quality_score > result.current.quality_score
    assert result.changed


def test_same_unloading_and_next_loading_location_is_rewarded():
    provider = MatrixRouteProvider({(1, 2): (20.0, 30), (2, 3): (20.0, 30)})
    first = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T09:00", "2026-07-22T07:00", "2026-07-22T11:00")
    second = _order(2, "B", 2, 3, "2026-07-22T08:00", "2026-07-22T12:00", "2026-07-22T09:00", "2026-07-22T14:00")

    plan = MultiStopTourOptimizer(provider).evaluate(
        [first, second], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert plan.total_transfer_minutes == 0
    assert any("direkter Standortübergang" in text for text in plan.explanations)


def test_time_window_violation_marks_plan_as_critical():
    provider = MatrixRouteProvider({(1, 2): (20.0, 180)})
    order = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T06:30", "2026-07-22T07:00", "2026-07-22T08:00")

    plan = MultiStopTourOptimizer(provider).evaluate(
        [order], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert not plan.feasible
    assert plan.quality_label == "kritisch"
    assert any("Entladezeitfenster" in item.message for item in plan.violations)


def test_missing_route_data_is_marked_as_estimated_not_as_distance():
    first = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T12:00", "2026-07-22T07:00", "2026-07-22T14:00")
    second = _order(2, "B", 3, 4, "2026-07-22T10:00", "2026-07-22T18:00", "2026-07-22T11:00", "2026-07-22T20:00")

    plan = MultiStopTourOptimizer().evaluate(
        [first, second], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert plan.total_distance_km is None
    assert plan.estimated_route_legs == 3
    assert any("konservativ geschätzt" in text for text in plan.explanations)


def test_total_distance_contains_loaded_and_empty_legs():
    provider = MatrixRouteProvider({
        (1, 2): (100.0, 90),
        (2, 3): (25.0, 30),
        (3, 4): (80.0, 75),
    })
    first = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T09:00", "2026-07-22T07:00", "2026-07-22T12:00")
    second = _order(2, "B", 3, 4, "2026-07-22T10:00", "2026-07-22T13:00", "2026-07-22T11:00", "2026-07-22T16:00")

    plan = MultiStopTourOptimizer(provider).evaluate(
        [first, second], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert plan.loaded_distance_km == 180.0
    assert plan.empty_distance_km == 25.0
    assert plan.total_distance_km == 205.0
    assert plan.total_drive_minutes == 195


def test_result_reports_distance_and_time_saving():
    provider = MatrixRouteProvider({
        (1, 2): (40.0, 45), (3, 4): (40.0, 45), (5, 6): (40.0, 45),
        (2, 3): (100.0, 120), (4, 5): (100.0, 120),
        (2, 5): (10.0, 15), (6, 3): (10.0, 15),
    })
    a = _order(1, "A", 1, 2, "2026-07-22T06:00", "2026-07-22T08:00", "2026-07-22T07:00", "2026-07-22T10:00")
    b = _order(2, "B", 3, 4, "2026-07-22T12:00", "2026-07-22T15:00", "2026-07-22T13:00", "2026-07-22T18:00")
    c = _order(3, "C", 5, 6, "2026-07-22T09:00", "2026-07-22T11:00", "2026-07-22T10:00", "2026-07-22T13:00")

    result = MultiStopTourOptimizer(provider).optimize(
        [a, b, c], tour_start=datetime(2026, 7, 22, 6, 0)
    )

    assert result.distance_saving_km == 180.0
    assert result.time_saving_minutes == 210


def test_vehicle_start_location_is_included_in_empty_distance_and_sequence():
    provider = MatrixRouteProvider({
        # Fahrzeug steht an Standort 1 (Ettlingen).
        (1, 1): (0.0, 0),
        (1, 3): (100.0, 120),
        # Aufträge: A startet am Fahrzeugstandort, B führt zurück dorthin.
        (1, 2): (30.0, 30),
        (2, 3): (30.0, 30),
        (3, 1): (30.0, 30),
        (2, 1): (10.0, 10),
    })
    a = _order(1, "Ettlingen-Germersheim", 1, 2,
               "2026-07-22T06:00", "2026-07-22T08:00",
               "2026-07-22T06:30", "2026-07-22T10:00")
    b = _order(2, "Wöllstein-Ettlingen", 3, 1,
               "2026-07-22T10:00", "2026-07-22T14:00",
               "2026-07-22T11:00", "2026-07-22T16:00")

    result = MultiStopTourOptimizer(provider).optimize(
        [b, a],
        tour_start=datetime(2026, 7, 22, 6, 0),
        tour_start_location_id=1,
    )

    assert result.optimized.order_ids == (1, 2)
    assert result.optimized.stops[0].transfer_distance_km == 0.0
    assert any("Fahrzeugstandort" in text for text in result.optimized.explanations)


def test_optimizer_prefers_less_lateness_when_no_sequence_is_feasible():
    provider = MatrixRouteProvider({
        (1, 2): (10.0, 10), (3, 4): (10.0, 10),
        (2, 3): (10.0, 10), (4, 1): (10.0, 10),
        (9, 1): (0.0, 0), (9, 3): (90.0, 120),
    })
    early = _order(1, "Früh", 1, 2,
                   "2026-07-22T06:00", "2026-07-22T06:20",
                   "2026-07-22T06:10", "2026-07-22T07:30")
    late = _order(2, "Spät", 3, 4,
                  "2026-07-22T06:00", "2026-07-22T08:30",
                  "2026-07-22T06:10", "2026-07-22T10:00")

    result = MultiStopTourOptimizer(provider).optimize(
        [late, early],
        tour_start=datetime(2026, 7, 22, 6, 0),
        tour_start_location_id=9,
    )

    assert result.optimized.order_ids == (1, 2)
    assert result.optimized.total_lateness_minutes < result.current.total_lateness_minutes
