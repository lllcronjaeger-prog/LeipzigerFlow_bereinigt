from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.services.trailer_compatibility import parse_trailer_types


class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PlanningWarning:
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING


class TourWarningEngine:
    """Zentrale Prüfungen für Personal, Fahrzeug, Trailer und Tourzeitraum."""

    DUE_SOON_DAYS = 30

    def __init__(self, time_engine: TimePlanningEngine | None = None):
        self.time_engine = time_engine or TimePlanningEngine()

    def evaluate(self, tour, *, planning_date: date | None = None) -> list[PlanningWarning]:
        warnings: list[PlanningWarning] = []
        reference_date = planning_date or getattr(tour, "tour_date", None)
        schedule = self.time_engine.build_schedule(tour)
        starts_at, ends_at = schedule.start_at, schedule.end_at

        self._check_driver(tour, reference_date, warnings)
        self._check_vehicle(tour, starts_at, ends_at, reference_date, warnings)
        self._check_trailer(tour, starts_at, ends_at, reference_date, warnings)
        self._check_orders(tour, planning_date, warnings)
        return self._deduplicate(warnings)

    def _check_driver(self, tour, reference_date, warnings):
        assignments = list(getattr(tour, "driver_assignments", []) or [])
        driver = getattr(tour, "driver", None)
        if driver is None and not assignments:
            warnings.append(PlanningWarning("driver_missing", "Fahrer fehlt")); return
        if assignments:
            ordered = sorted(assignments, key=lambda item: item.starts_at)
            for index, item in enumerate(ordered):
                if item.ends_at <= item.starts_at:
                    warnings.append(PlanningWarning("driver_segment_invalid", "Fahrerabschnitt hat eine ungültige Zeit", WarningSeverity.ERROR))
                if index and ordered[index - 1].ends_at != item.starts_at:
                    warnings.append(PlanningWarning("driver_segment_gap", "Fahrerabschnitte sind nicht lückenlos", WarningSeverity.ERROR))
                if index and not (item.change_base_location_id or str(item.change_base_name or "").strip()):
                    warnings.append(PlanningWarning("driver_change_without_base", "Fahrerwechsel ohne Basis", WarningSeverity.ERROR))
            driver = getattr(ordered[0], "driver", None) or driver
        if not getattr(driver, "active", True):
            warnings.append(PlanningWarning("driver_inactive", "Fahrer ist inaktiv", WarningSeverity.ERROR))
        valid_until = getattr(driver, "license_valid_until", None)
        if valid_until and reference_date and valid_until < reference_date:
            warnings.append(PlanningWarning("license_expired", "Führerschein abgelaufen", WarningSeverity.ERROR))

    def _check_vehicle(self, tour, starts_at, ends_at, reference_date, warnings):
        vehicle = getattr(tour, "vehicle", None)
        if vehicle is None:
            warnings.append(PlanningWarning("vehicle_missing", "Fahrzeug fehlt")); return
        if not getattr(vehicle, "active", True):
            warnings.append(PlanningWarning("vehicle_inactive", "Fahrzeug ist inaktiv", WarningSeverity.ERROR))
        self._check_due_date("vehicle_hu", "Fahrzeug-HU", getattr(vehicle, "hu_date", None), reference_date, warnings)
        self._check_absences("vehicle", "Fahrzeug", getattr(vehicle, "absences", ()), starts_at, ends_at, warnings)
        self._check_double_booking("vehicle", "Fahrzeug", getattr(vehicle, "tours", ()), tour, starts_at, ends_at, warnings)

    def _check_trailer(self, tour, starts_at, ends_at, reference_date, warnings):
        trailer = getattr(tour, "trailer", None) or getattr(getattr(tour, "vehicle", None), "trailer", None)
        if trailer is None:
            warnings.append(PlanningWarning("trailer_missing", "Trailer fehlt")); return
        if not getattr(trailer, "active", True):
            warnings.append(PlanningWarning("trailer_inactive", "Trailer ist inaktiv", WarningSeverity.ERROR))
        self._check_due_date("trailer_hu", "Trailer-HU", getattr(trailer, "hu_date", None), reference_date, warnings)
        self._check_due_date("trailer_sp", "Trailer-SP", getattr(trailer, "sp_date", None), reference_date, warnings)
        self._check_absences("trailer", "Trailer", getattr(trailer, "absences", ()), starts_at, ends_at, warnings)
        self._check_double_booking("trailer", "Trailer", getattr(trailer, "tours", ()), tour, starts_at, ends_at, warnings)

        vehicle = getattr(tour, "vehicle", None)
        if vehicle is not None and not getattr(vehicle, "is_mega", False) and getattr(trailer, "is_mega", False):
            warnings.append(PlanningWarning(
                "vehicle_trailer_incompatible",
                "Standard-Zugmaschine darf keinen Mega-Trailer ziehen",
                WarningSeverity.ERROR,
            ))
        actual_type = getattr(trailer, "trailer_type", "")
        for position in getattr(tour, "positions", ()):
            order = getattr(position, "transport_order", None)
            if order is None: continue
            allowed = parse_trailer_types(getattr(order, "required_trailer_type", "Plane"))
            if actual_type and actual_type not in allowed:
                warnings.append(PlanningWarning(
                    "trailer_type_incompatible",
                    f"Auftrag {order.order_number}: Trailer {actual_type} passt nicht zur Anforderung {', '.join(allowed)}",
                    WarningSeverity.ERROR,
                ))

    def _check_absences(self, prefix, label, absences, starts_at, ends_at, warnings):
        for absence in absences:
            if not getattr(absence, "active", True): continue
            absence_start = getattr(absence, "starts_at", None); absence_end = getattr(absence, "ends_at", None)
            if not absence_start or not absence_end: continue
            if absence_start < ends_at and starts_at < absence_end:
                reason = getattr(absence, "reason", "Sperrzeit")
                remarks = str(getattr(absence, "remarks", "") or "").strip()
                detail = f" – {remarks}" if remarks else ""
                warnings.append(PlanningWarning(
                    f"{prefix}_absence",
                    f"{label} gesperrt: {reason}, {absence_start:%d.%m.%Y %H:%M} bis {absence_end:%d.%m.%Y %H:%M}{detail}",
                    WarningSeverity.ERROR,
                ))

    def _check_double_booking(self, prefix, label, tours, current_tour, starts_at, ends_at, warnings):
        for other in tours:
            if getattr(other, "id", None) == getattr(current_tour, "id", None): continue
            if str(getattr(other, "status", "")).casefold() in {"storniert", "erledigt", "archiviert"}: continue
            try:
                other_schedule = self.time_engine.build_schedule(other)
            except Exception:
                continue
            if other_schedule.start_at < ends_at and starts_at < other_schedule.end_at:
                warnings.append(PlanningWarning(
                    f"{prefix}_double_booking",
                    f"{label} bereits in Tour {other.tour_number} eingesetzt ({other_schedule.start_at:%d.%m. %H:%M} bis {other_schedule.end_at:%d.%m. %H:%M})",
                    WarningSeverity.ERROR,
                ))

    def _check_due_date(self, code, label, due_date, reference_date, warnings):
        if not due_date or not reference_date: return
        if due_date < reference_date:
            warnings.append(PlanningWarning(code + "_expired", f"{label} abgelaufen ({due_date:%d.%m.%Y})", WarningSeverity.ERROR))
        elif due_date <= reference_date + timedelta(days=self.DUE_SOON_DAYS):
            days = (due_date - reference_date).days
            warnings.append(PlanningWarning(code + "_soon", f"{label} läuft in {days} Tagen ab ({due_date:%d.%m.%Y})"))

    def _check_orders(self, tour, planning_date, warnings):
        if not getattr(tour, "positions", None):
            warnings.append(PlanningWarning("tour_empty", "Tour enthält keine Aufträge", WarningSeverity.INFO))
        for position in getattr(tour, "positions", ()):
            order = getattr(position, "transport_order", None)
            if order is None: continue
            if order.unloading_date < order.loading_date:
                warnings.append(PlanningWarning("invalid_order_dates", f"Auftrag {order.order_number}: Entladung vor Beladung", WarningSeverity.ERROR))
            if planning_date and order.loading_date != planning_date:
                warnings.append(PlanningWarning("different_loading_date", f"Auftrag {order.order_number}: Beladung am {order.loading_date:%d.%m.%Y}", WarningSeverity.INFO))

    @staticmethod
    def _deduplicate(items):
        result = []; seen = set()
        for item in items:
            key = (item.code, item.message)
            if key not in seen:
                seen.add(key); result.append(item)
        return result
