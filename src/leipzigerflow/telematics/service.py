from __future__ import annotations

from datetime import datetime

from leipzigerflow.telematics.event_engine import TelematicsEventEngine
from leipzigerflow.telematics.models import StatusSuggestion, TelematicsEvent, VehiclePosition
from leipzigerflow.telematics.provider import TelematicsProvider


class TelematicsService:
    """Koordiniert Provider, Zwischenspeicher, Ereignisse und Statusvorschläge."""

    def __init__(self, provider: TelematicsProvider) -> None:
        self.provider = provider
        self.event_engine = TelematicsEventEngine()
        self.positions_by_plate: dict[str, VehiclePosition] = {}
        self.last_sync_at: datetime | None = None

    def synchronize(self, tours=()) -> tuple[list[TelematicsEvent], list[StatusSuggestion]]:
        positions = self.provider.fetch_positions(since=self.last_sync_at)
        events = self.event_engine.ingest(positions)
        for position in positions:
            self.positions_by_plate[position.license_plate.strip().casefold()] = position
        suggestions: list[StatusSuggestion] = []
        for event in events:
            for tour in tours:
                suggestion = self.event_engine.suggest_tour_status(tour, event)
                if suggestion is not None:
                    suggestions.append(suggestion)
        if positions:
            self.last_sync_at = max(position.recorded_at for position in positions)
        return events, suggestions

    def latest_position(self, license_plate: str) -> VehiclePosition | None:
        return self.positions_by_plate.get(license_plate.strip().casefold())
