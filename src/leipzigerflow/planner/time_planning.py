from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import math
import re
from typing import Any, Protocol

from leipzigerflow.config.settings import AVERAGE_SPEED, ROUTING_DEFAULT_DURATION_MINUTES


class RouteProvider(Protocol):
    def route(self, origin_location_id: int, destination_location_id: int) -> Any: ...


@dataclass(frozen=True, slots=True)
class _FallbackRouteLeg:
    distance_km: float | None
    duration_minutes: int
    estimated: bool = True


@dataclass(slots=True)
class PlannedStop:
    sequence: int
    order_id: int
    order_number: str
    kind: str
    location_name: str
    planned_arrival: datetime
    planned_departure: datetime
    window_from: datetime | None = None
    window_until: datetime | None = None
    conflict: str = ""


@dataclass(slots=True)
class PlannedTravel:
    sequence: int
    origin_name: str
    destination_name: str
    started_at: datetime
    ended_at: datetime
    distance_km: float | None
    driving_minutes: int
    estimated: bool = False
    partial: bool = False
    day_number: int = 1
    is_empty_run: bool = False


@dataclass(slots=True)
class PlannedBreak:
    started_at: datetime
    ended_at: datetime
    minutes: int
    reason: str
    is_daily_rest: bool = False


@dataclass(slots=True)
class DutyDay:
    day_number: int
    started_at: datetime
    ended_at: datetime
    driving_minutes: int = 0
    working_minutes: int = 0
    break_minutes: int = 0

    @property
    def shift_minutes(self) -> int:
        return max(0, int((self.ended_at - self.started_at).total_seconds() // 60))


@dataclass(slots=True)
class _BreakState:
    continuous_driving: int = 0
    working_since_break: int = 0
    daily_working: int = 0
    daily_driving: int = 0
    credited_break: int = 0
    duty_started_at: datetime | None = None
    day_number: int = 1


@dataclass(slots=True)
class TourSchedule:
    tour_id: int
    start_at: datetime
    end_at: datetime
    stops: list[PlannedStop] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    travels: list[PlannedTravel] = field(default_factory=list)
    breaks: list[PlannedBreak] = field(default_factory=list)
    duty_days: list[DutyDay] = field(default_factory=list)
    total_driving_minutes: int = 0
    total_distance_km: float | None = 0.0

    @property
    def deployment_days(self) -> int:
        """Kalendertage vom Tourbeginn bis zum Tourende, jeweils einschließlich."""
        return max(1, (self.end_at.date() - self.start_at.date()).days + 1)

    @property
    def overnight_count(self) -> int:
        return max(0, self.deployment_days - 1)


class TimePlanningEngine:
    """Mehrtägige Tourzeitplanung mit Pausen und täglicher Ruhezeit.

    Fahrtabschnitte dürfen über einen Tageswechsel geteilt werden. Nach dem
    letzten Lade-/Entladevorgang fährt der Fahrer mit der verbleibenden Lenk-
    und Schichtzeit weiter in Richtung des nächsten Ziels. Erst wenn eine
    Tagesgrenze erreicht ist, wird eine tägliche Ruhezeit eingeplant und der
    Restabschnitt am Folgetag fortgesetzt.
    """

    DEFAULT_START = time(6, 0)
    DEFAULT_SERVICE_MINUTES = 60
    CONTINUOUS_DRIVING_LIMIT_MINUTES = 270
    DRIVING_BREAK_MINUTES = 45
    WORKING_TIME_LIMIT_MINUTES = 360
    WORKING_TIME_BREAK_MINUTES = 30
    LONG_WORKING_DAY_MINUTES = 540
    LONG_WORKING_DAY_BREAK_MINUTES = 45
    DAILY_DRIVING_LIMIT_MINUTES = 540
    MAX_SHIFT_MINUTES = 15 * 60
    DAILY_REST_MINUTES = 11 * 60

    def __init__(self, route_provider: RouteProvider | None = None, *, average_speed_kmh: float = AVERAGE_SPEED,
                 fallback_duration_minutes: int = ROUTING_DEFAULT_DURATION_MINUTES) -> None:
        self._route_provider = route_provider
        self.average_speed_kmh = max(1.0, float(average_speed_kmh))
        self.fallback_duration_minutes = max(0, int(fallback_duration_minutes))

    @property
    def route_provider(self) -> RouteProvider:
        if self._route_provider is None:
            from leipzigerflow.routing.service import get_default_routing_service
            self._route_provider = get_default_routing_service()
        return self._route_provider

    def build_schedule(self, tour) -> TourSchedule:
        start_at = datetime.combine(tour.tour_date, getattr(tour, "planned_start_time", None) or self.DEFAULT_START)
        previous_available_at = getattr(tour, "previous_available_at", None)
        current = max(start_at, previous_available_at) if isinstance(previous_available_at, datetime) else start_at
        schedule_start_at = current
        stops: list[PlannedStop] = []
        travels: list[PlannedTravel] = []
        breaks: list[PlannedBreak] = []
        warnings: list[str] = []
        duty_days: list[DutyDay] = []
        driver = getattr(tour, "driver", None)
        state = _BreakState(
            continuous_driving=max(0, int(getattr(driver, "continuous_driving_minutes", 0) or 0)),
            working_since_break=max(0, int(getattr(driver, "working_since_break_minutes", 0) or 0)),
            daily_working=max(0, int(getattr(driver, "daily_working_minutes", 0) or 0)),
            daily_driving=max(0, int(getattr(driver, "daily_driving_minutes", 0) or 0)),
            duty_started_at=current,
        )
        total_driving = state.daily_driving
        total_distance = 0.0
        distance_complete = True
        previous_location = getattr(tour, "previous_location", None)
        if previous_location is None:
            # Eine Tour ohne expliziten Vorgänger beginnt am Heimatstandort des
            # Fahrzeugs. So wird die Leerfahrt zur ersten Ladestelle in jeder
            # vollständigen Tour- und Fahreransicht sichtbar und zeitlich
            # berücksichtigt, nicht nur in der Simulationsvorschau.
            vehicle_at_start = getattr(tour, "vehicle", None)
            previous_location = getattr(vehicle_at_start, "home_base_location", None)
        travel_sequence = 0

        positions = sorted(tour.positions, key=lambda p: (p.position or 0, p.id or 0))
        for sequence, position in enumerate(positions, start=1):
            order = position.transport_order
            loading_location = order.loading_location
            unloading_location = order.unloading_location

            if previous_location is not None and loading_location is not None:
                travel_sequence += 1
                current, driven, distance = self._add_travel(
                    current, previous_location, loading_location, travel_sequence,
                    state, travels, breaks, warnings, duty_days, is_empty_run=True,
                )
                total_driving += driven
                if distance is None: distance_complete = False
                else: total_distance += distance

            current, loading_stop = self._make_stop(
                sequence, order, "Laden", loading_location,
                order.loading_date, order.loading_time_from, order.loading_time_until,
                getattr(loading_location, "loading_duration_minutes", self.DEFAULT_SERVICE_MINUTES),
                current, state, breaks, duty_days,
                flexible=bool(getattr(order, "loading_time_flexible", False)),
                open_from=getattr(order, "loading_open_from", None),
                open_until=getattr(order, "loading_open_until", None),
            )
            stops.append(loading_stop)
            if loading_stop.conflict: warnings.append(loading_stop.conflict)

            if loading_location is not None and unloading_location is not None:
                travel_sequence += 1
                current, driven, distance = self._add_travel(
                    current, loading_location, unloading_location, travel_sequence,
                    state, travels, breaks, warnings, duty_days, is_empty_run=False,
                )
                total_driving += driven
                if distance is None: distance_complete = False
                else: total_distance += distance

            current, unloading_stop = self._make_stop(
                sequence, order, "Entladen", unloading_location,
                order.unloading_date, order.unloading_time_from, order.unloading_time_until,
                getattr(unloading_location, "unloading_duration_minutes", self.DEFAULT_SERVICE_MINUTES),
                current, state, breaks, duty_days,
                flexible=bool(getattr(order, "unloading_time_flexible", False)),
                open_from=getattr(order, "unloading_open_from", None),
                open_until=getattr(order, "unloading_open_until", None),
            )
            stops.append(unloading_stop)
            if unloading_stop.conflict: warnings.append(unloading_stop.conflict)
            previous_location = unloading_location

        # Nahverkehr und jede Schicht eines Wechselfahrerfahrzeugs enden
        # zwingend an der Heimatbasis. Die Rückfahrt ist eine technische
        # Leerfahrt: Sie zählt nicht als Transportauftrag, wird aber in
        # Strecke, Lenkzeit, Arbeitszeit, Tourende und Restkapazität geführt.
        vehicle = getattr(tour, "vehicle", None)
        profile = getattr(vehicle, "staffing_profile", None)
        operation_type = str(getattr(vehicle, "operation_type", "") or "").casefold()
        is_local = operation_type == "nahverkehr"
        has_relief_shift = bool(
            profile
            and getattr(profile, "sequential_double_shift", False)
            and getattr(profile, "relief_driver_id", None)
        )
        return_required = bool(
            vehicle
            and (
                is_local
                or getattr(vehicle, "daily_return_required", False)
                or has_relief_shift
            )
        )
        home_base_location = getattr(vehicle, "home_base_location", None) if vehicle else None
        if return_required:
            if home_base_location is None:
                base_label = str(getattr(vehicle, "home_base", "Ettlingen") or "Ettlingen")
                warnings.append(
                    f"Rückkehr zur Basis {base_label} ist vorgeschrieben, aber der Basis ist kein Standort zugeordnet."
                )
            elif previous_location is not None and getattr(previous_location, "id", None) != getattr(home_base_location, "id", None):
                travel_sequence += 1
                current, driven, distance = self._add_travel(
                    current, previous_location, home_base_location, travel_sequence,
                    state, travels, breaks, warnings, duty_days, is_empty_run=True,
                )
                total_driving += driven
                if distance is None:
                    distance_complete = False
                else:
                    total_distance += distance
                stops.append(PlannedStop(
                    sequence=len(positions) + 1,
                    order_id=0,
                    order_number="",
                    kind="Basisrückkehr",
                    location_name=(
                        getattr(home_base_location, "full_display", "")
                        or getattr(home_base_location, "name", "")
                        or str(getattr(vehicle, "home_base", "Ettlingen") or "Ettlingen")
                    ),
                    planned_arrival=current,
                    planned_departure=current,
                ))
                previous_location = home_base_location

        self._close_day(current, state, duty_days)
        if any(travel.estimated for travel in travels):
            warnings.append("Mindestens ein Fahrtabschnitt konnte nicht vollständig geroutet werden; die gekennzeichnete Ersatzfahrzeit wurde verwendet.")
        deployment_days = max(1, (current.date() - schedule_start_at.date()).days + 1)
        if deployment_days > 1:
            warnings.append(f"Tour erstreckt sich über {deployment_days} Einsatztage; tägliche Ruhezeiten und Wartezeiten sind berücksichtigt.")

        return TourSchedule(int(tour.id), schedule_start_at, current, stops, warnings, travels, breaks, duty_days,
                            total_driving_minutes=total_driving,
                            total_distance_km=round(total_distance, 1) if distance_complete else None)

    def _shift_remaining(self, current: datetime, state: _BreakState) -> int:
        if state.duty_started_at is None: return self.MAX_SHIFT_MINUTES
        elapsed = int((current - state.duty_started_at).total_seconds() // 60)
        return max(0, self.MAX_SHIFT_MINUTES - elapsed)

    def _add_travel(self, current, origin, destination, sequence, state, travels, breaks, warnings, duty_days, *, is_empty_run=False):
        leg = self._route_leg(origin, destination)
        total_minutes = self._driving_minutes(leg)
        remaining = total_minutes
        total_distance = leg.distance_km
        driven_total = 0
        segment_index = 0
        origin_name = getattr(origin, "name", "Start") or "Start"
        destination_name = getattr(destination, "name", "Ziel") or "Ziel"

        while remaining > 0:
            driving_available = min(
                self.CONTINUOUS_DRIVING_LIMIT_MINUTES - state.continuous_driving,
                self.DAILY_DRIVING_LIMIT_MINUTES - state.daily_driving,
            )
            work_available = self.WORKING_TIME_LIMIT_MINUTES - state.working_since_break
            shift_available = self._shift_remaining(current, state)
            sunday_boundary = self._minutes_until_sunday(current)
            available = min(driving_available, work_available, shift_available, sunday_boundary)

            if available <= 0:
                daily_limit = state.daily_driving >= self.DAILY_DRIVING_LIMIT_MINUTES or shift_available <= 0
                if daily_limit:
                    current = self._insert_daily_rest(current, state, breaks, duty_days, destination_name)
                else:
                    reason_is_driving = (self.CONTINUOUS_DRIVING_LIMIT_MINUTES - state.continuous_driving) <= work_available
                    current = self._insert_break(
                        current,
                        self.DRIVING_BREAK_MINUTES if reason_is_driving else self.WORKING_TIME_BREAK_MINUTES,
                        "Fahrtunterbrechung nach 4:30 h Lenkzeit" if reason_is_driving else "Arbeitszeitpause nach spätestens 6 Stunden",
                        state, breaks,
                    )
                continue

            driven_now = min(remaining, available)
            segment_start = current
            current += timedelta(minutes=driven_now)
            state.continuous_driving += driven_now
            state.working_since_break += driven_now
            state.daily_working += driven_now
            state.daily_driving += driven_now
            remaining -= driven_now
            driven_total += driven_now
            segment_index += 1
            partial = remaining > 0
            seg_origin = origin_name if segment_index == 1 else f"Zwischenstopp Richtung {destination_name}"
            seg_destination = destination_name if not partial else f"Zwischenstopp Richtung {destination_name}"
            seg_distance = None
            if total_distance is not None and total_minutes > 0:
                seg_distance = round(float(total_distance) * driven_now / total_minutes, 1)
            travels.append(PlannedTravel(sequence, seg_origin, seg_destination, segment_start, current,
                                         seg_distance, driven_now, leg.estimated or leg.distance_km is None,
                                         partial=partial, day_number=state.day_number,
                                         is_empty_run=is_empty_run))

        if leg.distance_km is None:
            warnings.append(f"Route {origin_name} → {destination_name}: Entfernung nicht berechenbar; Ersatzfahrzeit {total_minutes} Minuten.")
        return current, driven_total, total_distance

    @staticmethod
    def _minutes_until_sunday(current: datetime) -> int:
        """Minutes until the Sunday driving ban starts (Sunday 00:00)."""
        if current.weekday() == 6:
            return 0
        days_until_sunday = (6 - current.weekday()) % 7
        sunday_start = datetime.combine(current.date() + timedelta(days=days_until_sunday), time.min)
        return max(0, int((sunday_start - current).total_seconds() // 60))

    def _skip_sunday(self, current, state, breaks, duty_days):
        """Block all driving and operational work on Sundays.

        The waiting interval is a weekly rest and therefore never contributes
        to driver working-time utilization.
        """
        if current.weekday() != 6:
            return current
        if state.daily_working > 0 or state.daily_driving > 0:
            self._close_day(current, state, duty_days)
        monday = datetime.combine(current.date() + timedelta(days=1), time.min)
        minutes = max(0, int((monday - current).total_seconds() // 60))
        if minutes:
            breaks.append(PlannedBreak(current, monday, minutes, "Sonntagsfahrverbot / Wochenruhe", True))
        state.day_number += 1
        state.continuous_driving = 0
        state.working_since_break = 0
        state.daily_working = 0
        state.daily_driving = 0
        state.credited_break = 0
        state.duty_started_at = monday
        return monday

    def _insert_break(self, current, minutes, reason, state, breaks):
        start = current
        current += timedelta(minutes=minutes)
        breaks.append(PlannedBreak(start, current, minutes, reason))
        state.credited_break += minutes
        state.working_since_break = 0
        if minutes >= self.DRIVING_BREAK_MINUTES: state.continuous_driving = 0
        return current

    def _close_day(self, current, state, duty_days):
        if state.duty_started_at is None: return
        if duty_days and duty_days[-1].day_number == state.day_number: return
        duty_days.append(DutyDay(state.day_number, state.duty_started_at, current,
                                 driving_minutes=state.daily_driving,
                                 working_minutes=state.daily_working,
                                 break_minutes=state.credited_break))

    def _insert_daily_rest(self, current, state, breaks, duty_days, destination_name=""):
        self._close_day(current, state, duty_days)
        start = current
        current += timedelta(minutes=self.DAILY_REST_MINUTES)
        reason = "Tägliche Ruhezeit"
        if destination_name: reason += f" am Zwischenstopp Richtung {destination_name}"
        breaks.append(PlannedBreak(start, current, self.DAILY_REST_MINUTES, reason, is_daily_rest=True))
        state.day_number += 1
        state.continuous_driving = 0
        state.working_since_break = 0
        state.daily_working = 0
        state.daily_driving = 0
        state.credited_break = 0
        state.duty_started_at = current
        return current

    def _add_work(self, current, minutes, state, breaks, duty_days):
        remaining = max(0, int(minutes)); started = current
        while remaining > 0:
            current = self._skip_sunday(current, state, breaks, duty_days)
            work_available = self.WORKING_TIME_LIMIT_MINUTES - state.working_since_break
            shift_available = self._shift_remaining(current, state)
            if shift_available <= 0:
                current = self._insert_daily_rest(current, state, breaks, duty_days)
                continue
            if work_available <= 0:
                current = self._insert_break(current, self.WORKING_TIME_BREAK_MINUTES,
                                             "Arbeitszeitpause nach spätestens 6 Stunden", state, breaks)
                continue
            sunday_boundary = self._minutes_until_sunday(current)
            worked = min(remaining, work_available, shift_available, sunday_boundary)
            if worked <= 0:
                current = self._skip_sunday(current, state, breaks, duty_days)
                continue
            current += timedelta(minutes=worked)
            state.working_since_break += worked
            state.daily_working += worked
            remaining -= worked
        if state.daily_working > self.LONG_WORKING_DAY_MINUTES and state.credited_break < self.LONG_WORKING_DAY_BREAK_MINUTES:
            current = self._insert_break(current, self.LONG_WORKING_DAY_BREAK_MINUTES-state.credited_break,
                                         "Zusätzliche Arbeitszeitpause bei mehr als 9 Stunden", state, breaks)
        return current, started

    def _make_stop(self, sequence, order, kind, location, stop_date, window_from, window_until, duration,
                   current, state, breaks, duty_days, *, flexible=False, open_from=None, open_until=None):
        booked_start = datetime.combine(stop_date, window_from) if window_from else None
        booked_end = datetime.combine(stop_date, window_until) if window_until else None
        location_open_start, location_open_end = self._opening_window(location, stop_date)
        order_open_start = datetime.combine(stop_date, open_from) if open_from else None
        order_open_end = datetime.combine(stop_date, open_until) if open_until else None

        # Flexible Zeitfenster sind eine Wunschzeit innerhalb der Öffnungszeit.
        # Gebuchte Termine bleiben dagegen harte Grenzen.
        if flexible:
            earliest_candidates = [value for value in (current, order_open_start, location_open_start) if value is not None]
            effective_start = max(earliest_candidates) if earliest_candidates else current
            latest = min(
                [value for value in (order_open_end, location_open_end) if value is not None],
                default=None,
            )
        else:
            earliest_candidates = [value for value in (current, booked_start, order_open_start, location_open_start) if value is not None]
            effective_start = max(earliest_candidates) if earliest_candidates else current
            latest = min(
                [value for value in (booked_end, order_open_end, location_open_end) if value is not None],
                default=None,
            )

        waiting = max(0, int((effective_start-current).total_seconds()//60))
        if waiting >= self.DAILY_REST_MINUTES:
            # Eine lange Wartezeit darf mehrere Kalendertage umfassen. Sie wird
            # als ein zusammenhängendes Ruhe-/Warteereignis gespeichert; die
            # Einsatztage werden aus dem realen Datumsbereich berechnet.
            self._close_day(current, state, duty_days)
            breaks.append(PlannedBreak(current, effective_start, waiting, "Wartezeit als tägliche Ruhezeit genutzt", True))
            elapsed_days = max(1, (effective_start.date() - current.date()).days)
            state.day_number += elapsed_days
            state.continuous_driving = state.working_since_break = state.daily_working = state.daily_driving = state.credited_break = 0
            state.duty_started_at = effective_start
        elif waiting >= 15:
            breaks.append(PlannedBreak(current, effective_start, waiting, "Warten auf Zeitfenster", False))
            state.credited_break += waiting
            state.working_since_break = 0
            if waiting >= self.DRIVING_BREAK_MINUTES:
                state.continuous_driving = 0

        conflict = ""
        if latest and effective_start > latest:
            conflict = f"{order.order_number}: {kind}-Zeitfenster bei {getattr(location,'name','Unbekannter Standort')} wird überschritten."
        departure, _ = self._add_work(effective_start, max(0, int(duration or self.DEFAULT_SERVICE_MINUTES)), state, breaks, duty_days)
        return departure, PlannedStop(
            sequence, int(order.id), order.order_number, kind,
            getattr(location, "name", "Unbekannter Standort") if location else "Unbekannter Standort",
            effective_start, departure, booked_start, booked_end, conflict,
        )

    def _route_leg(self, origin, destination):
        oid, did = getattr(origin, "id", None), getattr(destination, "id", None)
        if oid is None or did is None: return _FallbackRouteLeg(None, self.fallback_duration_minutes, True)
        try: return self.route_provider.route(int(oid), int(did))
        except Exception: return _FallbackRouteLeg(None, self.fallback_duration_minutes, True)

    def _driving_minutes(self, leg):
        if leg.distance_km is not None:
            return max(0, int(math.ceil(float(leg.distance_km)/self.average_speed_kmh*60.0)))
        return max(0, int(leg.duration_minutes or self.fallback_duration_minutes))

    @staticmethod
    def _opening_window(location, day: date):
        text = str(getattr(location, "opening_hours", "") or "").strip()
        if not text: return None, None
        match = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", text)
        if not match: return None, None
        return (datetime.combine(day, time(int(match.group(1)), int(match.group(2)))),
                datetime.combine(day, time(int(match.group(3)), int(match.group(4)))))
