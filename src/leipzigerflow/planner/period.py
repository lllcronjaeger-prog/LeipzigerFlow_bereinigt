from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class PlanningPeriodMode(str, Enum):
    DAY = "day"
    WEEK = "week"


@dataclass(frozen=True, slots=True)
class PlanningPeriod:
    start: date
    end: date
    mode: PlanningPeriodMode

    @classmethod
    def day(cls, value: date) -> "PlanningPeriod":
        return cls(value, value, PlanningPeriodMode.DAY)

    @classmethod
    def week(cls, value: date) -> "PlanningPeriod":
        start = value - timedelta(days=value.weekday())
        return cls(start, start + timedelta(days=6), PlanningPeriodMode.WEEK)

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end
