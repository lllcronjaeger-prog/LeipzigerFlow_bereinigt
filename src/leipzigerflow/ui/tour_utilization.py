from __future__ import annotations

from dataclasses import dataclass


DEFAULT_DAILY_WORK_MINUTES = 10 * 60


@dataclass(frozen=True, slots=True)
class TourTimeUtilization:
    work_minutes: int
    capacity_minutes: int
    utilization_percent: float
    driving_minutes: int
    deployment_days: int

    @property
    def work_text(self) -> str:
        return f"{self._format(self.work_minutes)} / {self._format(self.capacity_minutes)}"

    @property
    def driving_text(self) -> str:
        return self._format(self.driving_minutes)

    @property
    def status_text(self) -> str:
        if self.utilization_percent > 100:
            return "Arbeitszeit überschritten"
        if self.utilization_percent >= 80:
            return "sehr gute Auslastung"
        if self.utilization_percent >= 60:
            return "gute Auslastung"
        return "noch freie Arbeitszeit"

    @property
    def status_icon(self) -> str:
        if self.utilization_percent > 100:
            return "🔴"
        if self.utilization_percent >= 80:
            return "🟢"
        if self.utilization_percent >= 60:
            return "🟡"
        return "🟠"

    @staticmethod
    def _format(minutes: int) -> str:
        hours, remainder = divmod(max(0, int(minutes)), 60)
        return f"{hours:d}:{remainder:02d} h"


def calculate_tour_time_utilization(tour, schedule) -> TourTimeUtilization:
    """Calculate the dispatcher's primary utilization from driver working time.

    The planned duty time, not payload, is the headline value. A 10-hour
    productive working day is used as the default planning target. Where a
    vehicle staffing profile defines a shift length, that configured value is
    respected. Multi-day tours receive one target per deployment day.
    """

    profile = getattr(getattr(tour, "vehicle", None), "staffing_profile", None)
    # Die Touren-des-Tages-Ansicht verwendet verbindlich den betrieblichen
    # Planungswert von 10 Stunden je Fahrer und Einsatztag. Ältere
    # Stammdatensätze können noch 540 Minuten enthalten; diese dürfen die
    # Anzeige nicht wieder auf 9 Stunden zurücksetzen.
    configured_minutes = int(
        getattr(profile, "shift_minutes", 0) or DEFAULT_DAILY_WORK_MINUTES
    )
    daily_capacity = max(DEFAULT_DAILY_WORK_MINUTES, configured_minutes)
    if bool(getattr(profile, "sequential_double_shift", False)) and getattr(
        profile, "relief_driver_id", None
    ):
        daily_capacity *= 2

    duty_days = list(getattr(schedule, "duty_days", []) or [])

    # Auf der Tageskarte ist die Auslastung des stärksten tatsächlichen
    # Arbeitstags relevant. Kalenderwartezeiten, tägliche Ruhezeiten,
    # Wochenenden und Übernachtungen dürfen weder den Zähler noch den Nenner
    # aufblasen. DutyDay.working_minutes enthält nur Fahrt und sonstige Arbeit.
    daily_work_values = [
        max(0, int(getattr(day, "working_minutes", 0) or 0))
        for day in duty_days
    ]
    positive_work_days = [minutes for minutes in daily_work_values if minutes > 0]
    work_minutes = max(positive_work_days, default=0)

    # Kompatibilitäts-Fallback für ältere/vereinfachte Schedule-Objekte ohne
    # working_minutes: auch dort wird der stärkste einzelne Einsatztag gezeigt.
    if work_minutes <= 0 and duty_days:
        work_minutes = max(
            (max(0, int(getattr(day, "shift_minutes", 0) or 0)) for day in duty_days),
            default=0,
        )
    if work_minutes <= 0:
        work_minutes = max(
            0,
            round((schedule.end_at - schedule.start_at).total_seconds() / 60),
        )

    assignments = list(getattr(tour, "driver_assignments", []) or [])
    if assignments:
        # Bei Fahrerwechseln zählt für die Belastungsanzeige der längste
        # tatsächliche Fahrerabschnitt, nicht die gesamte Fahrzeuglaufzeit.
        segment_minutes = [
            max(0, int((item.ends_at - item.starts_at).total_seconds() // 60))
            for item in assignments
            if getattr(item, "starts_at", None) and getattr(item, "ends_at", None)
        ]
        if segment_minutes:
            work_minutes = max(segment_minutes)
        daily_capacity = max(DEFAULT_DAILY_WORK_MINUTES, configured_minutes)

    deployment_days = max(1, len(positive_work_days) or len(duty_days) or 1)
    # Die Prozentanzeige bezieht sich immer auf einen Fahrertag mit 10 Stunden.
    # Mehrtägige Touren werden nicht gegen 20/30/... Stunden verglichen.
    capacity_minutes = daily_capacity
    utilization = (work_minutes / capacity_minutes * 100.0) if capacity_minutes else 0.0

    return TourTimeUtilization(
        work_minutes=work_minutes,
        capacity_minutes=capacity_minutes,
        utilization_percent=utilization,
        driving_minutes=max(0, int(getattr(schedule, "total_driving_minutes", 0) or 0)),
        deployment_days=deployment_days,
    )
