from __future__ import annotations

from datetime import date, datetime

from leipzigerflow.planner.engine.state_resolver import ResolvedResourceState, ResourceStateResolver


class VehicleStateService:
    """Zentraler Einstiegspunkt für den Tagesstartzustand eines Fahrzeugs.

    Die bestehende, fachlich bewährte Resolver-Logik bleibt erhalten. Andere
    Module sollen den Zustand künftig über diesen Service beziehen, damit keine
    parallelen Standort- und Basisregeln entstehen.
    """

    def __init__(self, resolver: ResourceStateResolver | None = None):
        self.resolver = resolver or ResourceStateResolver()

    def resolve_day_start(
        self,
        vehicle,
        driver,
        planning_day: date,
        duty_start: datetime,
        last_tour=None,
        known_locations=(),
    ) -> ResolvedResourceState:
        return self.resolver.resolve(
            vehicle,
            driver,
            planning_day,
            duty_start,
            last_tour,
            known_locations,
        )
