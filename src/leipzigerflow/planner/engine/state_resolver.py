from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from leipzigerflow.services.rotation_manager import DriverWorkModel, RotationManager


@dataclass(frozen=True, slots=True)
class ResolvedResourceState:
    return_to_base_required: bool
    home_base_location: object | None
    home_base_label: str
    start_location: object | None
    start_at: datetime
    reason: str


class ResourceStateResolver:
    """Ermittelt den echten Tageszustand einer Fahrzeug-/Fahrerkombination.

    Regeln:
    * Nahverkehr startet und endet täglich an der Heimatbasis.
    * Fernverkehr behält an Werktagen seinen letzten operativen Standort.
    * Nach einem Wochenende beginnt auch Fernverkehr wieder an der Basis.
    * Ein Mo–Fr-Arbeitsmodell erzwingt alleine keine tägliche Rückkehr; der
      Einsatztyp des Fahrers/Fahrzeugs ist maßgeblich.
    * Die Fahrerbasis hat Vorrang vor der Fahrzeugbasis.
    """

    LOCAL = "nahverkehr"
    LONG_HAUL = "fernverkehr"

    def __init__(self, rotation_manager: RotationManager | None = None):
        self.rotation_manager = rotation_manager or RotationManager()

    def resolve(self, vehicle, driver, planning_day: date, duty_start: datetime, last_tour=None, known_locations=()):
        vehicle_operation = self._normalized(getattr(vehicle, "operation_type", ""))
        driver_operation = self._normalized(getattr(driver, "allowed_operation", ""))
        vehicle_local = vehicle_operation == self.LOCAL
        driver_local = driver_operation == self.LOCAL
        explicit_longhaul = driver_operation == self.LONG_HAUL or vehicle_operation == self.LONG_HAUL

        profile = getattr(vehicle, "staffing_profile", None)
        relief = bool(
            profile
            and getattr(profile, "sequential_double_shift", False)
            and getattr(profile, "relief_driver_id", None)
        )

        # Fernverkehr mit Fernverkehrsfahrer darf werktags auswärts ruhen. Eine
        # alte daily_return_required-Einstellung des Fahrzeugs darf das nicht
        # versehentlich überschreiben.
        return_required = bool(vehicle_local or driver_local or relief)
        if not explicit_longhaul:
            return_required = return_required or bool(getattr(vehicle, "daily_return_required", False))

        driver_base = getattr(driver, "home_base_location", None)
        vehicle_base = getattr(vehicle, "home_base_location", None)
        base = driver_base or vehicle_base
        base_label = self._location_label(base)
        if not base_label:
            base_label = (
                str(getattr(driver, "home_base", "") or "").strip()
                or str(getattr(vehicle, "home_base", "") or "").strip()
                or "Ettlingen"
            )
        if base is None:
            base = self._match_location(base_label, known_locations)

        last_location = self._last_location(last_tour)
        weekend_reset = self._weekend_reset_required(planning_day, last_tour, driver)
        if return_required:
            start_location = base
            reason = f"Nahverkehr: Tagesstart an Heimatbasis {base_label}; Rückkehr am selben Arbeitstag zwingend."
        elif weekend_reset:
            start_location = base
            reason = f"Wochenend-Rückführung: Tagesstart an Heimatbasis {base_label}."
        else:
            start_location = last_location or base
            reason = "Fernverkehr: tatsächlicher Endstandort des letzten Werktags wird übernommen."

        return ResolvedResourceState(
            return_to_base_required=return_required,
            home_base_location=base,
            home_base_label=base_label,
            start_location=start_location,
            start_at=duty_start,
            reason=reason,
        )

    def _weekend_reset_required(self, planning_day: date, last_tour, driver) -> bool:
        if planning_day.weekday() != 0:
            if last_tour is None or getattr(last_tour, "tour_date", None) is None:
                return False
            return (planning_day - last_tour.tour_date).days >= 3

        # Ein Montag allein setzt den Fernverkehrsstandort nicht mehr pauschal
        # zurück. In 2/1- und 3/1-Modellen bleibt der Standort erhalten, wenn
        # derselbe Fahrer lediglich seine zweite/dritte Einsatzwoche beginnt.
        # Nur der Beginn eines neuen Zyklus oder ein tatsächlicher Fahrerwechsel
        # startet an der Heimatbasis.
        model = str(getattr(driver, "work_model", "") or "")
        if model in {DriverWorkModel.TWO_ONE.value, DriverWorkModel.THREE_ONE.value}:
            try:
                status = self.rotation_manager.status(driver, planning_day)
            except Exception:
                status = None
            last_driver_id = getattr(last_tour, "driver_id", None) if last_tour is not None else None
            current_driver_id = getattr(driver, "id", None)
            driver_changed = (
                last_driver_id is not None
                and current_driver_id is not None
                and int(last_driver_id) != int(current_driver_id)
            )
            starts_new_cycle = bool(status and status.available and status.working_week == 1)
            return driver_changed or starts_new_cycle

        # MO-FR-Fahrer kehren nach dem Wochenende weiterhin zur Basis zurück.
        return True

    @staticmethod
    def _last_location(tour):
        if tour is None or not getattr(tour, "positions", None):
            return None
        for position in reversed(tour.positions):
            order = getattr(position, "transport_order", None)
            location = getattr(order, "unloading_location", None)
            if location is not None:
                return location
        return None

    @classmethod
    def _match_location(cls, label: str, locations):
        wanted = cls._normalized(label)
        if not wanted:
            return None
        exact, partial = [], []
        for location in locations:
            values = (getattr(location, "name", ""), getattr(location, "city", ""), getattr(location, "full_display", ""))
            normalized = [cls._normalized(value) for value in values if value]
            if wanted in normalized:
                exact.append(location)
            elif any(wanted in value or value in wanted for value in normalized if value):
                partial.append(location)
        return (exact or partial or [None])[0]

    @staticmethod
    def _location_label(location) -> str:
        if location is None:
            return ""
        return str(getattr(location, "full_display", "") or getattr(location, "name", "") or "").strip()

    @staticmethod
    def _normalized(value) -> str:
        return " ".join(str(value or "").casefold().replace("-", " ").split())
