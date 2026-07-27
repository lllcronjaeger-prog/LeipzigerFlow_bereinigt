from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from collections import defaultdict


class ResourceKind(str, Enum):
    DRIVER = "driver"
    VEHICLE = "vehicle"


@dataclass(frozen=True, slots=True)
class ResourceConflict:
    planning_date: date
    kind: ResourceKind
    resource_id: int
    resource_name: str
    tour_ids: tuple[int, ...]

    @property
    def message(self) -> str:
        label = "Fahrer" if self.kind == ResourceKind.DRIVER else "Fahrzeug"
        return f"{label} doppelt eingeplant: {self.resource_name}"


class ResourceConflictEngine:
    """Erkennt Doppelbelegungen von Fahrern und Fahrzeugen pro Kalendertag."""

    def evaluate(self, tours) -> list[ResourceConflict]:
        grouped: dict[tuple[date, ResourceKind, int], list] = defaultdict(list)
        names: dict[tuple[date, ResourceKind, int], str] = {}

        for tour in tours:
            if getattr(tour, "status", "") == "Storniert":
                continue
            planning_date = getattr(tour, "tour_date", None)
            if planning_date is None:
                continue

            driver_id = getattr(tour, "driver_id", None)
            if driver_id:
                key = (planning_date, ResourceKind.DRIVER, int(driver_id))
                grouped[key].append(tour)
                names[key] = getattr(tour, "driver_display", "") or f"Fahrer #{driver_id}"

            vehicle_id = getattr(tour, "vehicle_id", None)
            if vehicle_id:
                key = (planning_date, ResourceKind.VEHICLE, int(vehicle_id))
                grouped[key].append(tour)
                names[key] = getattr(tour, "vehicle_display", "") or f"Fahrzeug #{vehicle_id}"

        conflicts: list[ResourceConflict] = []
        for key, assigned_tours in grouped.items():
            if len(assigned_tours) < 2:
                continue
            planning_date, kind, resource_id = key
            conflicts.append(
                ResourceConflict(
                    planning_date=planning_date,
                    kind=kind,
                    resource_id=resource_id,
                    resource_name=names[key],
                    tour_ids=tuple(sorted(int(tour.id) for tour in assigned_tours)),
                )
            )
        return sorted(conflicts, key=lambda item: (item.planning_date, item.kind.value, item.resource_name))

    def messages_by_tour(self, tours) -> dict[int, list[str]]:
        result: dict[int, list[str]] = defaultdict(list)
        for conflict in self.evaluate(tours):
            for tour_id in conflict.tour_ids:
                result[tour_id].append(conflict.message)
        return dict(result)
