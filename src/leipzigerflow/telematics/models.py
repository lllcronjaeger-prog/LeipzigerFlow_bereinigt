from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MovementState(str, Enum):
    UNKNOWN = "unknown"
    PARKED = "parked"
    MOVING = "moving"
    IDLING = "idling"


class TelematicsEventType(str, Enum):
    POSITION_UPDATED = "position_updated"
    MOVEMENT_STARTED = "movement_started"
    MOVEMENT_STOPPED = "movement_stopped"
    GEOFENCE_ENTERED = "geofence_entered"
    GEOFENCE_LEFT = "geofence_left"


@dataclass(frozen=True, slots=True)
class VehiclePosition:
    external_vehicle_id: str
    license_plate: str
    latitude: float
    longitude: float
    recorded_at: datetime
    speed_kmh: float = 0.0
    heading_degrees: float | None = None
    movement_state: MovementState = MovementState.UNKNOWN
    driver_name: str = ""
    odometer_km: float | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True, slots=True)
class TelematicsEvent:
    event_type: TelematicsEventType
    position: VehiclePosition
    occurred_at: datetime
    previous_position: VehiclePosition | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StatusSuggestion:
    tour_id: int
    suggested_tour_status: str
    reason: str
    confidence: float
    order_ids: tuple[int, ...] = ()
    source: str = "telematics"
