from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from leipzigerflow.services.rotation_manager import RotationManager


@dataclass(frozen=True, slots=True)
class DriverAvailability:
    day: date
    available: bool
    phase: str
    reason: str
    available_until: date | None
    next_change: date | None


class DriverAvailabilityService:
    """Einheitlicher Abgleich aus Modulon-Sperren und rechnerischem Arbeitsmodell."""

    def __init__(self) -> None:
        self.rotation = RotationManager()

    def status(self, driver, day: date) -> DriverAvailability:
        status = self.rotation.status(driver, day)
        available_until = None
        if status.available:
            available_until = self.continuous_available_until(driver, day)
        return DriverAvailability(
            day=day,
            available=status.available,
            phase=status.phase,
            reason=status.reason,
            available_until=available_until,
            next_change=status.next_phase_change,
        )

    def continuous_available_until(self, driver, start: date, max_days: int = 120) -> date | None:
        if not self.rotation.status(driver, start).available:
            return None
        current = start
        for _ in range(max_days):
            next_day = current + timedelta(days=1)
            if not self.rotation.status(driver, next_day).available:
                return current
            current = next_day
        return current
