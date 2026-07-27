from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class DriverWorkModel(StrEnum):
    MONDAY_FRIDAY = "MO-FR"
    TWO_ONE = "2/1"
    THREE_ONE = "3/1"


@dataclass(frozen=True, slots=True)
class RotationStatus:
    day: date
    available: bool
    phase: str
    cycle_day: int
    cycle_length: int
    working_week: int | None
    reason: str
    next_phase_change: date | None


class RotationManager:
    """Computes driver system weeks without storing recurring calendar rows."""

    def status(self, driver, day: date) -> RotationStatus:
        if not bool(getattr(driver, "active", True)):
            return RotationStatus(day, False, "Inaktiv", 0, 0, None, "Fahrer ist inaktiv", None)
        absence_from = getattr(driver, "absence_from", None)
        absence_until = getattr(driver, "absence_until", None)
        if absence_from and absence_until and absence_from <= day <= absence_until:
            reason = str(getattr(driver, "absence_reason", "Abwesend") or "Abwesend")
            return RotationStatus(day, False, reason, 0, 0, None, reason, absence_until + timedelta(days=1))

        model = str(getattr(driver, "work_model", DriverWorkModel.MONDAY_FRIDAY.value) or DriverWorkModel.MONDAY_FRIDAY.value)
        if model == DriverWorkModel.MONDAY_FRIDAY.value:
            available = day.weekday() < 5
            return RotationStatus(day, available, "Einsatz" if available else "Wochenende", day.weekday()+1, 7, 1 if available else None,
                                  "Regulärer Arbeitstag" if available else "MO-FR-Fahrer am Wochenende frei",
                                  day + timedelta(days=(5-day.weekday()) if available else (7-day.weekday())))

        start = getattr(driver, "rotation_start", None)
        if start is None:
            return RotationStatus(day, False, "Unvollständig", 0, 0, None, "Rotationsbeginn fehlt", None)
        work_weeks = 2 if model == DriverWorkModel.TWO_ONE.value else 3
        cycle_days = (work_weeks + 1) * 7
        offset = (day - start).days % cycle_days
        available = offset < work_weeks * 7
        phase = f"Einsatzwoche {offset // 7 + 1} von {work_weeks}" if available else "Freiwoche"
        change_in = (work_weeks * 7 - offset) if available else (cycle_days - offset)
        return RotationStatus(day, available, phase, offset+1, cycle_days, offset//7+1 if available else None,
                              "Systemwoche berechnet" if available else "Fahrer befindet sich in der Freiwoche",
                              day + timedelta(days=change_in))
