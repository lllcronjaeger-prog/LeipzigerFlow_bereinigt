from __future__ import annotations

from datetime import date
from typing import Any

from leipzigerflow.planner.engine.models import PlanningStrategy
from leipzigerflow.planner.engine.reporting import (
    PlanningKpiSummary,
    PlanningReplay,
    ReplayStep,
    build_planning_replay,
    evaluate_planning_result,
)
from leipzigerflow.planner.engine.service import DispatchSimulationService


class PlanningEngine:
    """Public facade for UI, tests and future integrations."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self.service = DispatchSimulationService(session)

    def simulate(self, planning_day: date) -> Any:
        return self.service.simulate(planning_day)

    def simulate_horizon(
        self,
        start_day: date,
        horizon_days: int = 3,
        *,
        strategy: PlanningStrategy = PlanningStrategy.MAX_UTILIZATION,
    ) -> Any:
        return self.service.simulate_horizon(
            start_day,
            horizon_days=horizon_days,
            strategy=strategy,
        )

    def apply(self, result: Any, planning_day: date) -> tuple[int, int]:
        return self.service.apply(result, planning_day)

    def apply_horizon(self, result: Any) -> tuple[int, int]:
        return self.service.apply_horizon(result)

    @staticmethod
    def evaluate(result: Any) -> PlanningKpiSummary:
        return evaluate_planning_result(result)

    @staticmethod
    def replay(result: Any) -> PlanningReplay:
        return build_planning_replay(result)


__all__ = [
    "PlanningEngine",
    "PlanningKpiSummary",
    "PlanningReplay",
    "ReplayStep",
]
