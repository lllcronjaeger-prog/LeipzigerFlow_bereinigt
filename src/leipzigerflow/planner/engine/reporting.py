from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable


@dataclass(slots=True)
class PlanningKpiSummary:
    assigned_orders: int
    open_orders: int
    utilized_vehicles: int
    proposed_tours: int
    empty_run_minutes: int
    waiting_minutes: int
    average_score: float
    utilization_percent: float
    simulation_seconds: float
    suggestions: int


@dataclass(slots=True)
class ReplayStep:
    sequence: int
    phase: str
    message: str
    details: str = ""
    planning_day: date | None = None


@dataclass(slots=True)
class PlanningReplay:
    steps: list[ReplayStep] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.steps


def evaluate_planning_result(result: Any) -> PlanningKpiSummary:
    """Create a stable KPI view from any planning result object."""
    return PlanningKpiSummary(
        assigned_orders=int(getattr(result, "assigned_count", 0)),
        open_orders=int(getattr(result, "open_count", 0)),
        utilized_vehicles=int(getattr(result, "utilized_vehicle_count", 0)),
        proposed_tours=int(getattr(result, "proposed_tour_count", 0)),
        empty_run_minutes=int(getattr(result, "total_transfer_minutes", 0)),
        waiting_minutes=int(getattr(result, "total_waiting_minutes", 0)),
        average_score=float(getattr(result, "average_score", 0.0)),
        utilization_percent=float(getattr(result, "utilization_percent", 0.0)),
        simulation_seconds=float(getattr(result, "simulation_seconds", 0.0)),
        suggestions=int(getattr(result, "suggestion_count", 0)),
    )


def build_planning_replay(result: Any) -> PlanningReplay:
    """Build a chronological replay for single-day and horizon results."""
    daily_results = getattr(result, "daily_results", None)
    if isinstance(daily_results, dict):
        return PlanningReplay(
            steps=_build_horizon_steps(daily_results.items()),
        )

    return PlanningReplay(
        steps=_build_trace_steps(
            getattr(result, "planning_trace", []) or [],
        )
    )


def _build_horizon_steps(
    daily_results: Iterable[tuple[date, Any]],
) -> list[ReplayStep]:
    steps: list[ReplayStep] = []
    sequence = 1

    for planning_day, day_result in sorted(daily_results):
        trace = getattr(day_result, "planning_trace", []) or []
        for entry in trace:
            steps.append(
                _replay_step(
                    sequence=sequence,
                    entry=entry,
                    planning_day=planning_day,
                )
            )
            sequence += 1

    return steps


def _build_trace_steps(trace: Iterable[Any]) -> list[ReplayStep]:
    return [
        _replay_step(sequence=sequence, entry=entry)
        for sequence, entry in enumerate(trace, start=1)
    ]


def _replay_step(
    *,
    sequence: int,
    entry: Any,
    planning_day: date | None = None,
) -> ReplayStep:
    return ReplayStep(
        sequence=sequence,
        phase=_phase_value(entry),
        message=str(getattr(entry, "message", "")),
        details=str(getattr(entry, "details", "")),
        planning_day=planning_day,
    )


def _phase_value(entry: Any) -> str:
    phase = getattr(entry, "phase", "")
    return str(getattr(phase, "value", phase))
