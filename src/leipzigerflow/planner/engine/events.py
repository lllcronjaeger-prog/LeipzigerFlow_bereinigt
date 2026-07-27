from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Iterable


class PlanningEventType(StrEnum):
    NEW_ORDER = "Neuer Auftrag"
    TOUR_COMPLETED = "Tour abgeschlossen"
    VEHICLE_AVAILABLE = "Fahrzeug verfügbar"
    VEHICLE_DEFECT = "Fahrzeug defekt"
    DRIVER_UNAVAILABLE = "Fahrer nicht verfügbar"
    TRAFFIC_DELAY = "Verkehrsverzögerung"
    TIME_WINDOW_CHANGED = "Zeitfenster geändert"
    MANUAL_CHANGE = "Manuelle Dispositionsänderung"


@dataclass(frozen=True, slots=True)
class PlanningEvent:
    event_type: PlanningEventType
    occurred_at: datetime
    entity_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplanningScope:
    full_replanning: bool = False
    order_ids: frozenset[int] = frozenset()
    vehicle_ids: frozenset[int] = frozenset()
    tour_ids: frozenset[int] = frozenset()
    reasons: tuple[str, ...] = ()


class PlanningEventManager:
    """Ermittelt aus Ereignissen den kleinstmöglichen Neuplanungsbereich."""

    def determine_scope(self, events: Iterable[PlanningEvent]) -> ReplanningScope:
        orders: set[int] = set()
        vehicles: set[int] = set()
        tours: set[int] = set()
        reasons: list[str] = []
        full = False

        for event in events:
            reasons.append(event.event_type.value)
            entity_id = event.entity_id
            if event.event_type is PlanningEventType.NEW_ORDER and entity_id is not None:
                orders.add(entity_id)
            elif event.event_type in {
                PlanningEventType.VEHICLE_AVAILABLE,
                PlanningEventType.VEHICLE_DEFECT,
            } and entity_id is not None:
                vehicles.add(entity_id)
            elif event.event_type is PlanningEventType.TOUR_COMPLETED and entity_id is not None:
                tours.add(entity_id)
                vehicle_id = event.payload.get("vehicle_id")
                if vehicle_id is not None:
                    vehicles.add(int(vehicle_id))
            elif event.event_type is PlanningEventType.TIME_WINDOW_CHANGED and entity_id is not None:
                orders.add(entity_id)
            elif event.event_type is PlanningEventType.TRAFFIC_DELAY:
                tour_id = event.payload.get("tour_id", entity_id)
                if tour_id is not None:
                    tours.add(int(tour_id))
            elif event.event_type is PlanningEventType.DRIVER_UNAVAILABLE:
                vehicle_id = event.payload.get("vehicle_id")
                if vehicle_id is not None:
                    vehicles.add(int(vehicle_id))
            elif event.event_type is PlanningEventType.MANUAL_CHANGE:
                full = bool(event.payload.get("full_replanning", False))
                order_id = event.payload.get("order_id")
                if order_id is not None:
                    orders.add(int(order_id))
                vehicle_id = event.payload.get("vehicle_id")
                if vehicle_id is not None:
                    vehicles.add(int(vehicle_id))

        return ReplanningScope(
            full_replanning=full,
            order_ids=frozenset(orders),
            vehicle_ids=frozenset(vehicles),
            tour_ids=frozenset(tours),
            reasons=tuple(dict.fromkeys(reasons)),
        )
