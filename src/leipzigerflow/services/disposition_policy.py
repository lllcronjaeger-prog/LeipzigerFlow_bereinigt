from __future__ import annotations

from dataclasses import dataclass

from leipzigerflow.models.vehicle import VehicleOperationType


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    feasible: bool
    reasons: tuple[str, ...]


class DispositionPolicy:
    """Combines vehicle operation profile and driver authorization."""
    def evaluate_end_of_day(self, vehicle, driver, end_location: str, is_overnight: bool) -> PolicyDecision:
        reasons=[]
        operation=str(getattr(vehicle, "operation_type", VehicleOperationType.LOCAL.value) or VehicleOperationType.LOCAL.value)
        allowed=str(getattr(driver, "allowed_operation", "Beides") or "Beides") if driver is not None else "Beides"
        if allowed not in {"Beides", operation}:
            reasons.append(f"Fahrer ist nicht für {operation} freigegeben")
        home=str(getattr(vehicle, "home_base", "Ettlingen") or "Ettlingen").strip().lower()
        if operation == VehicleOperationType.LOCAL.value:
            if is_overnight: reasons.append("Nahverkehr erlaubt keine auswärtige Tagesruhe")
            if home and home not in (end_location or "").strip().lower(): reasons.append(f"Nahverkehr muss an der Basis {getattr(vehicle, 'home_base', 'Ettlingen')} enden")
        elif is_overnight and not bool(getattr(vehicle, "overnight_away_allowed", True)):
            reasons.append("Auswärtige Tagesruhe ist für dieses Fahrzeug gesperrt")
        return PolicyDecision(not reasons, tuple(reasons))
