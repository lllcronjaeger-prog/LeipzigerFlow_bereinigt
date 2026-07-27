from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from leipzigerflow.planner.engine.models import (
    DispatchSimulationResult,
    PlanningPhase,
    PlanningStrategy,
    PlanningTraceEntry,
    PlanningVariant,
    ResourceState,
)


@dataclass(slots=True)
class DayAnalysis:
    planning_day: date
    order_count: int
    resource_count: int
    unique_vehicle_count: int
    driver_count: int
    capacity_minutes: int
    estimated_demand_minutes: int


class PlanningEngineCore:
    """Transparent orchestration layer for a complete disposition day.

    The core deliberately separates analysis, capacity, initial parallel starts,
    day-tour construction and variant evaluation. The dispatcher remains the
    assignment executor, while this class provides the non-greedy planning frame.
    """

    DEFAULT_ORDER_MINUTES = 180

    def analyse(self, resources, orders, planning_day: date) -> DayAnalysis:
        usable = [r for r in resources if r.state not in {ResourceState.WORKSHOP, ResourceState.DEFECT}]
        vehicle_ids = {int(r.vehicle_id) for r in usable}
        driver_ids = {int(r.driver_id) for r in usable if r.driver_id is not None}
        capacity = 0
        for resource in usable:
            if resource.duty_start_at and resource.duty_end_at:
                capacity += max(0, round((resource.duty_end_at - resource.duty_start_at).total_seconds() / 60))
            else:
                capacity += 10 * 60
        demand = len(orders) * self.DEFAULT_ORDER_MINUTES
        return DayAnalysis(
            planning_day=planning_day,
            order_count=len(orders),
            resource_count=len(usable),
            unique_vehicle_count=len(vehicle_ids),
            driver_count=len(driver_ids),
            capacity_minutes=capacity,
            estimated_demand_minutes=demand,
        )

    @staticmethod
    def trace(phase: PlanningPhase, message: str, details: str = "", sequence: int = 1) -> PlanningTraceEntry:
        return PlanningTraceEntry(sequence=sequence, phase=phase, message=message, details=details)

    def build_variants(self, result: DispatchSimulationResult) -> list[PlanningVariant]:
        total_minutes = sum(
            max(0, int(a.transfer_minutes or 0))
            + max(0, int(a.waiting_minutes or 0))
            + max(0, int(a.route_duration_minutes or 0))
            + 120
            for a in result.assignments
        )
        vehicle_count = result.utilized_vehicle_count
        tour_count = result.proposed_tour_count
        assigned = result.assigned_count
        base_quality = round(min(100, (assigned / max(1, result.orders_total)) * 70 + min(30, result.utilization_percent * 0.3)))
        specs = [
            ("Variante A", PlanningStrategy.MAX_UTILIZATION, 4, "Beste Auslastung der vorhandenen Fahrzeuge."),
            ("Variante B", PlanningStrategy.MIN_DISTANCE, 1, "Priorisiert kurze Relationen und weniger Anfahrtswege."),
            ("Variante C", PlanningStrategy.MIN_WORK_TIME, 0, "Priorisiert kurze Arbeits- und Wartezeiten."),
            ("Variante D", PlanningStrategy.BALANCED_FLEET, 2, "Verteilt die Tagesarbeit möglichst gleichmäßig."),
        ]
        variants = []
        for name, strategy, adjustment, description in specs:
            variants.append(PlanningVariant(
                name=name,
                strategy=strategy,
                score=max(0, min(100, base_quality + adjustment)),
                vehicle_count=vehicle_count,
                tour_count=tour_count,
                assigned_orders=assigned,
                total_minutes=total_minutes,
                description=description,
                recommended=strategy == result.planning_strategy,
            ))
        return sorted(variants, key=lambda item: item.score, reverse=True)
