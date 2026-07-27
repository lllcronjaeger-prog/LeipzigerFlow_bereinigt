from __future__ import annotations

from datetime import date
from typing import Iterable

from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.events import PlanningEvent, PlanningEventManager
from leipzigerflow.planner.engine.optimizer import OptimizationProfile
from leipzigerflow.planner.engine.resource_manager import ResourceManager


class DynamicDispatchEngine:
    """Orchestriert ereignisgetriebene Teil-Neuplanungen ohne Datenbankzugriff."""

    def __init__(self, dispatcher: AutomaticDispatcher | None = None):
        self.dispatcher = dispatcher or AutomaticDispatcher()
        self.event_manager = PlanningEventManager()

    def replan(
        self,
        resources,
        orders,
        planning_day: date,
        events: Iterable[PlanningEvent],
        profile: OptimizationProfile = OptimizationProfile.BALANCED,
    ):
        scope = self.event_manager.determine_scope(events)
        resource_manager = ResourceManager(list(resources))
        selected_resources = (
            resource_manager.all()
            if scope.full_replanning or not scope.vehicle_ids
            else resource_manager.affected(scope.vehicle_ids)
        )
        selected_orders = [
            order for order in orders
            if scope.full_replanning or not scope.order_ids or int(order.id) in scope.order_ids
        ]
        return self.dispatcher.simulate(
            selected_resources,
            selected_orders,
            planning_day,
            profile=profile,
            replanning_reasons=list(scope.reasons),
        )
