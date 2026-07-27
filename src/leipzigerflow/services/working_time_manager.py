from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True, slots=True)
class WorkingTimeBalance:
    day_minutes: int
    week_minutes: int
    double_week_minutes: int
    remaining_day_minutes: int
    remaining_week_minutes: int
    remaining_double_week_minutes: int
    required_break_minutes: int
    feasible: bool
    reasons: tuple[str, ...]


class WorkingTimeManager:
    """Central calculation for day, week and rolling double-week capacity."""
    DAILY_LIMIT_MINUTES = 600

    @staticmethod
    def required_break_minutes(work_minutes: int) -> int:
        if work_minutes > 9 * 60:
            return 45
        if work_minutes > 6 * 60:
            return 30
        return 0

    def evaluate(self, driver, planning_day: date, historical_minutes: dict[date, int], proposed_minutes: int = 0) -> WorkingTimeBalance:
        week_start = planning_day - timedelta(days=planning_day.weekday())
        double_start = week_start - timedelta(days=7)
        day = int(historical_minutes.get(planning_day, 0)) + proposed_minutes
        week = sum(int(v) for d, v in historical_minutes.items() if week_start <= d < week_start + timedelta(days=7)) + proposed_minutes
        double = sum(int(v) for d, v in historical_minutes.items() if double_start <= d < week_start + timedelta(days=7)) + proposed_minutes
        weekly_limit = int(getattr(driver, "weekly_target_minutes", 2880) or 2880)
        double_limit = int(getattr(driver, "double_week_limit_minutes", 5760) or 5760)
        breaks = self.required_break_minutes(day)
        reasons=[]
        if day + breaks > self.DAILY_LIMIT_MINUTES: reasons.append("Tägliche Arbeitszeit einschließlich erforderlicher Pause überschritten")
        if week > weekly_limit: reasons.append("Wochenarbeitszeit überschritten")
        if double > double_limit: reasons.append("Arbeitszeit der Doppelwoche überschritten")
        return WorkingTimeBalance(day, week, double, max(0,self.DAILY_LIMIT_MINUTES-day-breaks), max(0,weekly_limit-week), max(0,double_limit-double), breaks, not reasons, tuple(reasons))
