from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from leipzigerflow.planner.engine.models import ResourceAvailability, ResourceState


class ResourceManager:
    """Hält abgeleitete Ressourcenzustände während eines Planungslaufs konsistent."""

    def __init__(self, resources: list[ResourceAvailability]):
        self._resources = {resource.vehicle_id: resource for resource in resources}

    def all(self) -> list[ResourceAvailability]:
        return list(self._resources.values())

    def affected(self, vehicle_ids: set[int] | frozenset[int]) -> list[ResourceAvailability]:
        if not vehicle_ids:
            return self.all()
        return [self._resources[item] for item in vehicle_ids if item in self._resources]

    def mark_defect(self, vehicle_id: int, reason: str = "Fahrzeug als defekt gemeldet") -> None:
        resource = self._resources[vehicle_id]
        self._resources[vehicle_id] = replace(resource, state=ResourceState.DEFECT, reason=reason)

    def apply_delay(self, vehicle_id: int, delay_minutes: int) -> None:
        resource = self._resources[vehicle_id]
        self._resources[vehicle_id] = replace(
            resource,
            available_at=resource.available_at + timedelta(minutes=max(0, delay_minutes)),
            reason=f"Verfügbarkeit um {max(0, delay_minutes)} Minuten verschoben.",
        )
