from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from leipzigerflow.telematics.models import VehiclePosition


class TelematicsProviderError(RuntimeError):
    pass


class TelematicsNotConfiguredError(TelematicsProviderError):
    pass


class TelematicsProvider(ABC):
    """Austauschbare Schnittstelle für Spedion und weitere Telematikanbieter."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch_positions(self, since: datetime | None = None) -> list[VehiclePosition]:
        raise NotImplementedError
