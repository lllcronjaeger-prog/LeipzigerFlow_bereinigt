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


def calculate_tour_time_utilization(tour, schedule, planning_date=None) -> TourTimeUtilization:
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

    # Eine leere vorbereitete Tagestour besitzt noch keine operative Arbeitszeit.
    # Fahrerabschnitte oder ein 06:00–06:00-Platzhalter dürfen die Anzeige nicht
    # auf mehrere Tage bzw. hunderte Stunden aufblasen.
    if hasattr(tour, "positions") and not list(getattr(tour, "positions", []) or []):
        return TourTimeUtilization(
            work_minutes=0,
            capacity_minutes=daily_capacity,
            utilization_percent=0.0,
            driving_minutes=0,
            deployment_days=1,
        )

    # Auf der Tageskarte ist die Auslastung des stärksten tatsächlichen
    # Arbeitstags relevant. Kalenderwartezeiten, tägliche Ruhezeiten,
    # Wochenenden und Übernachtungen dürfen weder den Zähler noch den Nenner
    # aufblasen. DutyDay.working_minutes enthält nur Fahrt und sonstige Arbeit.
    daily_work_values = [
        max(0, int(getattr(day, "working_minutes", 0) or 0))
        for day in duty_days
    ]
    positive_work_days = [minutes for minutes in daily_work_values if minutes > 0]

    # In der Tagesplantafel darf nur Arbeit des angezeigten Kalendertags
    # erscheinen. Mehrtägige Touren werden deshalb anhand ihrer produktiven
    # Intervalle (Fahrt sowie Laden/Entladen) exakt an Mitternacht getrennt.
    # Aufträge des Folgetags erhöhen damit nicht mehr rückwirkend die
    # Auslastung des Tour-Starttags.
    work_minutes_for_date = None
    driving_minutes_for_date = None
    if planning_date is not None:
        from datetime import datetime, time, timedelta

        day_start = datetime.combine(planning_date, time.min)
        day_end = day_start + timedelta(days=1)

        def overlap_minutes(start, end):
            overlap_start = max(start, day_start)
            overlap_end = min(end, day_end)
            return max(0, int((overlap_end - overlap_start).total_seconds() // 60))

        travel_intervals = [
            (travel.started_at, travel.ended_at)
            for travel in list(getattr(schedule, "travels", []) or [])
            if getattr(travel, "started_at", None) and getattr(travel, "ended_at", None)
        ]
        stop_intervals = [
            (stop.planned_arrival, stop.planned_departure)
            for stop in list(getattr(schedule, "stops", []) or [])
            if getattr(stop, "planned_arrival", None) and getattr(stop, "planned_departure", None)
        ]
        work_minutes_for_date = sum(overlap_minutes(start, end) for start, end in travel_intervals + stop_intervals)
        driving_minutes_for_date = sum(overlap_minutes(start, end) for start, end in travel_intervals)

    work_minutes = (
        work_minutes_for_date
        if work_minutes_for_date is not None
        else max(positive_work_days, default=0)
    )

    # Kompatibilitäts-Fallback für ältere/vereinfachte Schedule-Objekte ohne
    # working_minutes: auch dort wird der stärkste einzelne Einsatztag gezeigt.
    if work_minutes <= 0 and duty_days and planning_date is None:
        work_minutes = max(
            (max(0, int(getattr(day, "shift_minutes", 0) or 0)) for day in duty_days),
            default=0,
        )
    if work_minutes <= 0 and planning_date is None:
        work_minutes = max(
            0,
            round((schedule.end_at - schedule.start_at).total_seconds() / 60),
        )

    assignments = list(getattr(tour, "driver_assignments", []) or [])
    active_assignments = []
    for item in assignments:
        starts_at = getattr(item, "starts_at", None)
        ends_at = getattr(item, "ends_at", None)
        if not starts_at or not ends_at:
            continue
        segment_start = max(starts_at, schedule.start_at)
        segment_end = min(ends_at, schedule.end_at)
        if segment_end > segment_start:
            active_assignments.append((item, segment_start, segment_end))

    # Fahrerabschnitte begrenzen die Anzeige nur bei einem echten Fahrerwechsel.
    # Ein einzelner importierter/Stammfahrerabschnitt darf die aus dem
    # Tourablauf berechnete Arbeitszeit nicht auf seine (ggf. veraltete)
    # Gültigkeitsdauer reduzieren. Bei mehreren Fahrern wird ausschließlich
    # produktive Zeit (Fahrt/Laden/Entladen), niemals Ruhe- oder Wartezeit,
    # anteilig auf die Fahrerabschnitte gerechnet.
    active_driver_ids = {
        int(getattr(item, "driver_id", 0) or 0)
        for item, _start, _end in active_assignments
        if getattr(item, "driver_id", None)
    }
    if len(active_driver_ids) > 1:
        productive_intervals = []
        for travel in list(getattr(schedule, "travels", []) or []):
            productive_intervals.append((travel.started_at, travel.ended_at))
        for stop in list(getattr(schedule, "stops", []) or []):
            productive_intervals.append((stop.planned_arrival, stop.planned_departure))
        if planning_date is not None:
            productive_intervals = [
                (max(start, day_start), min(end, day_end))
                for start, end in productive_intervals
                if min(end, day_end) > max(start, day_start)
            ]

        segment_work = []
        for _item, segment_start, segment_end in active_assignments:
            minutes = 0
            for interval_start, interval_end in productive_intervals:
                overlap_start = max(segment_start, interval_start)
                overlap_end = min(segment_end, interval_end)
                if overlap_end > overlap_start:
                    minutes += int((overlap_end - overlap_start).total_seconds() // 60)
            segment_work.append(minutes)
        if segment_work:
            work_minutes = max(segment_work)
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
        driving_minutes=(
            max(0, int(driving_minutes_for_date))
            if driving_minutes_for_date is not None
            else max(0, int(getattr(schedule, "total_driving_minutes", 0) or 0))
        ),
        deployment_days=deployment_days,
    )
