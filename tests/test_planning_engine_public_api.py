from types import SimpleNamespace

from leipzigerflow.planner.engine import (
    AutomaticTourBuilder,
    PlanningEngine,
    PlanningKpiSummary,
    PlanningReplay,
    ReplayStep,
)


def test_planning_engine_facade_is_part_of_public_api() -> None:
    assert PlanningEngine is not None
    assert PlanningKpiSummary is not None
    assert PlanningReplay is not None
    assert ReplayStep is not None
    assert AutomaticTourBuilder is not None


def test_evaluate_uses_safe_defaults_for_missing_metrics() -> None:
    summary = PlanningEngine.evaluate(SimpleNamespace(assigned_count=4, open_count=2))

    assert summary.assigned_orders == 4
    assert summary.open_orders == 2
    assert summary.proposed_tours == 0
    assert summary.average_score == 0.0


def test_replay_handles_single_day_trace() -> None:
    result = SimpleNamespace(
        planning_trace=[
            SimpleNamespace(
                phase=SimpleNamespace(value="assignment"),
                message="Auftrag zugeordnet",
                details="Fahrzeug 12",
            )
        ]
    )

    replay = PlanningEngine.replay(result)

    assert replay.is_empty is False
    assert replay.steps == [
        ReplayStep(
            sequence=1,
            phase="assignment",
            message="Auftrag zugeordnet",
            details="Fahrzeug 12",
        )
    ]


def test_replay_orders_horizon_days_and_keeps_continuous_sequence() -> None:
    from datetime import date

    result = SimpleNamespace(
        daily_results={
            date(2026, 7, 30): SimpleNamespace(
                planning_trace=[
                    SimpleNamespace(phase="apply", message="Tag 2", details="")
                ]
            ),
            date(2026, 7, 29): SimpleNamespace(
                planning_trace=[
                    SimpleNamespace(phase="start", message="Tag 1", details="")
                ]
            ),
        }
    )

    replay = PlanningEngine.replay(result)

    assert [step.sequence for step in replay.steps] == [1, 2]
    assert [step.message for step in replay.steps] == ["Tag 1", "Tag 2"]
    assert [step.planning_day for step in replay.steps] == [
        date(2026, 7, 29),
        date(2026, 7, 30),
    ]


def test_reporting_types_remain_importable_from_facade_module() -> None:
    from leipzigerflow.planner.engine.facade import (
        PlanningKpiSummary as FacadeKpiSummary,
        PlanningReplay as FacadeReplay,
        ReplayStep as FacadeReplayStep,
    )

    assert FacadeKpiSummary is PlanningKpiSummary
    assert FacadeReplay is PlanningReplay
    assert FacadeReplayStep is ReplayStep
