from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from leipzigerflow.planner.time_planning import TimePlanningEngine, TourSchedule


@dataclass(frozen=True, slots=True)
class DrivingRuleIssue:
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class DrivingRuleAssessment:
    estimated_driving_minutes: int
    estimated_shift_minutes: int
    required_break_minutes: int
    issues: list[DrivingRuleIssue] = field(default_factory=list)

    @property
    def driving_text(self) -> str:
        hours, minutes = divmod(self.estimated_driving_minutes, 60)
        return f"{hours:d}:{minutes:02d} h"

    @property
    def shift_text(self) -> str:
        hours, minutes = divmod(self.estimated_shift_minutes, 60)
        return f"{hours:d}:{minutes:02d} h"


class DrivingRulesEngine:
    """Transparente Vorprüfung der Lenk-, Arbeits- und Ruhezeiten.

    Grundlage ist der von ``TimePlanningEngine`` erzeugte reale Zeitstrahl.
    Fahrtunterbrechungen sind darin bereits zeitlich eingefügt. Vorhandene
    Wochenstände können später aus Telematik/Tachograph übernommen werden; bis
    dahin werden optionale Fahrerattribute verwendet und ansonsten null gesetzt.
    """

    CONTINUOUS_DRIVING_LIMIT_MINUTES = 270
    REGULAR_DAILY_DRIVING_LIMIT_MINUTES = 540
    EXTENDED_DAILY_DRIVING_LIMIT_MINUTES = 600
    WEEKLY_DRIVING_LIMIT_MINUTES = 56 * 60
    TWO_WEEK_DRIVING_LIMIT_MINUTES = 90 * 60
    BREAK_MINUTES = 45
    REGULAR_MAX_SHIFT_MINUTES = 13 * 60
    REDUCED_REST_MAX_SHIFT_MINUTES = 15 * 60
    REGULAR_DAILY_REST_MINUTES = 11 * 60
    REDUCED_DAILY_REST_MINUTES = 9 * 60

    def __init__(self, time_engine: TimePlanningEngine | None = None):
        self.time_engine = time_engine or TimePlanningEngine()

    def evaluate(self, tour, schedule: TourSchedule | None = None) -> DrivingRuleAssessment:
        schedule = schedule or self.time_engine.build_schedule(tour)
        driving_minutes = int(schedule.total_driving_minutes)
        duty_days = list(getattr(schedule, "duty_days", []) or [])
        shift_minutes = max((day.shift_minutes for day in duty_days), default=max(0, int((schedule.end_at - schedule.start_at) / timedelta(minutes=1))))
        required_break = sum(item.minutes for item in schedule.breaks if not getattr(item, "is_daily_rest", False))
        issues: list[DrivingRuleIssue] = []

        driver = getattr(tour, "driver", None)
        prior_week = max(0, int(getattr(driver, "weekly_driving_minutes", 0) or 0))
        prior_two_weeks = max(0, int(getattr(driver, "two_week_driving_minutes", 0) or 0))
        extended_days_used = max(0, int(getattr(driver, "extended_driving_days_used", 0) or 0))
        reduced_rests_used = max(0, int(getattr(driver, "reduced_daily_rests_used", 0) or 0))

        day_driving_values = [day.driving_minutes for day in duty_days] or [driving_minutes]
        for day_index, day_driving in enumerate(day_driving_values, start=1):
            if day_driving > self.EXTENDED_DAILY_DRIVING_LIMIT_MINUTES:
                issues.append(DrivingRuleIssue(
                    "daily_driving_exceeded",
                    f"Tag {day_index}: Lenkzeit {self._format(day_driving)} überschreitet 10:00 h.",
                    "error",
                ))
            elif day_driving > self.REGULAR_DAILY_DRIVING_LIMIT_MINUTES:
                severity = "error" if extended_days_used >= 2 else "warning"
                suffix = "; beide Verlängerungen dieser Woche sind bereits verbraucht." if severity == "error" else "; ein 10-Stunden-Lenktag ist erforderlich."
                issues.append(DrivingRuleIssue(
                    "extended_daily_driving",
                    f"Tag {day_index}: Lenkzeit {self._format(day_driving)}{suffix}",
                    severity,
                ))

        if required_break:
            issues.append(DrivingRuleIssue(
                "driving_break_planned",
                f"{self._format(required_break)} Fahrtunterbrechung wurde automatisch in die Tourzeit eingerechnet.",
                "info",
            ))

        for day in duty_days:
            if day.shift_minutes > self.REDUCED_REST_MAX_SHIFT_MINUTES:
                issues.append(DrivingRuleIssue(
                    "shift_too_long",
                    f"Tag {day.day_number}: Schichtdauer {self._format(day.shift_minutes)} überschreitet 15:00 h.",
                    "error",
                ))

        if prior_week + driving_minutes > self.WEEKLY_DRIVING_LIMIT_MINUTES:
            issues.append(DrivingRuleIssue(
                "weekly_driving_exceeded",
                f"Wochenlenkzeit würde {self._format(prior_week + driving_minutes)} erreichen und 56:00 h überschreiten.",
                "error",
            ))

        if prior_two_weeks + driving_minutes > self.TWO_WEEK_DRIVING_LIMIT_MINUTES:
            issues.append(DrivingRuleIssue(
                "two_week_driving_exceeded",
                f"Lenkzeit in zwei aufeinanderfolgenden Wochen würde {self._format(prior_two_weeks + driving_minutes)} erreichen und 90:00 h überschreiten.",
                "error",
            ))

        if self.REGULAR_MAX_SHIFT_MINUTES < shift_minutes <= self.REDUCED_REST_MAX_SHIFT_MINUTES:
            severity = "error" if reduced_rests_used >= 3 else "warning"
            issues.append(DrivingRuleIssue(
                "reduced_daily_rest_required",
                "Der folgende Dienstbeginn erfordert voraussichtlich eine reduzierte tägliche Ruhezeit von mindestens 9:00 h."
                if severity == "warning" else
                "Eine weitere reduzierte tägliche Ruhezeit ist zwischen den wöchentlichen Ruhezeiten nicht verfügbar.",
                severity,
            ))

        if any(travel.estimated for travel in schedule.travels):
            issues.append(DrivingRuleIssue(
                "estimated_route_sections",
                "Mindestens ein Fahrtabschnitt verwendet eine Ersatzfahrzeit, weil keine OSM-/Cache-Entfernung vorlag.",
                "info",
            ))

        return DrivingRuleAssessment(driving_minutes, shift_minutes, required_break, issues)

    @staticmethod
    def _format(minutes: int) -> str:
        hours, remainder = divmod(minutes, 60)
        return f"{hours:d}:{remainder:02d} h"
