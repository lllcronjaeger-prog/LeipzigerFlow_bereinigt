from __future__ import annotations

from collections.abc import Iterable

from leipzigerflow.telematics.models import (
    MovementState,
    StatusSuggestion,
    TelematicsEvent,
    TelematicsEventType,
    VehiclePosition,
)


class TelematicsEventEngine:
    """Erzeugt Ereignisse und vorsichtige Statusvorschläge aus GPS-Updates.

    Erledigt-Status werden bewusst nicht allein aus GPS-Daten gesetzt. Dafür ist
    später eine Fahrer-, POD- oder Geofence-Bestätigung vorgesehen.
    """

    def __init__(self) -> None:
        self._last_by_vehicle: dict[str, VehiclePosition] = {}

    def ingest(self, positions: Iterable[VehiclePosition]) -> list[TelematicsEvent]:
        events: list[TelematicsEvent] = []
        for position in positions:
            key = position.external_vehicle_id or position.license_plate.casefold()
            previous = self._last_by_vehicle.get(key)
            events.append(
                TelematicsEvent(
                    event_type=TelematicsEventType.POSITION_UPDATED,
                    position=position,
                    previous_position=previous,
                    occurred_at=position.recorded_at,
                )
            )
            if previous is not None:
                if previous.movement_state != MovementState.MOVING and position.movement_state == MovementState.MOVING:
                    events.append(
                        TelematicsEvent(
                            event_type=TelematicsEventType.MOVEMENT_STARTED,
                            position=position,
                            previous_position=previous,
                            occurred_at=position.recorded_at,
                        )
                    )
                elif previous.movement_state == MovementState.MOVING and position.movement_state != MovementState.MOVING:
                    events.append(
                        TelematicsEvent(
                            event_type=TelematicsEventType.MOVEMENT_STOPPED,
                            position=position,
                            previous_position=previous,
                            occurred_at=position.recorded_at,
                        )
                    )
            self._last_by_vehicle[key] = position
        return events

    @staticmethod
    def suggest_tour_status(tour, event: TelematicsEvent) -> StatusSuggestion | None:
        vehicle = getattr(tour, "vehicle", None)
        plate = str(getattr(vehicle, "license_plate", "")).strip().casefold()
        if not plate or plate != event.position.license_plate.strip().casefold():
            return None
        if event.event_type == TelematicsEventType.MOVEMENT_STARTED and tour.status == "Geplant":
            return StatusSuggestion(
                tour_id=tour.id,
                suggested_tour_status="Unterwegs",
                reason=f"Fahrzeug {event.position.license_plate} hat die Fahrt begonnen.",
                confidence=0.90,
                order_ids=tuple(position.transport_order_id for position in tour.positions),
            )
        return None
