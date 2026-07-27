from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TourQualityLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass(frozen=True, slots=True)
class TourQuality:
    level: TourQualityLevel
    score: int
    label: str


class TourQualityEngine:
    def evaluate(self, *, warnings=(), schedule_warnings=(), driving_issues=()) -> TourQuality:
        errors = sum(1 for item in warnings if getattr(getattr(item, "severity", None), "value", "") == "error")
        cautions = sum(1 for item in warnings if getattr(getattr(item, "severity", None), "value", "") == "warning")
        cautions += sum(1 for message in schedule_warnings if "überschritten" in str(message).lower())
        errors += sum(1 for item in driving_issues if getattr(item, "severity", "") == "error")
        cautions += sum(1 for item in driving_issues if getattr(item, "severity", "") == "warning")
        score = max(0, 100 - errors * 35 - cautions * 12)
        if errors:
            return TourQuality(TourQualityLevel.RED, score, "kritisch")
        if cautions:
            return TourQuality(TourQualityLevel.YELLOW, score, "prüfen")
        return TourQuality(TourQualityLevel.GREEN, score, "plausibel")
