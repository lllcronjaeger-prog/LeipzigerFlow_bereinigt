from __future__ import annotations

from datetime import date

from leipzigerflow.planner.engine.models import OrderCandidate, VehicleClass
from leipzigerflow.services.trailer_compatibility import parse_trailer_types, requires_mega_only


class OrderPriorityEngine:
    def build(self, order, planning_day: date) -> OrderCandidate:
        score = 0
        reasons: list[str] = []

        dispatch_priority = str(
            getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt") or "Eigenfuhrpark bevorzugt"
        )
        priority_points = {
            "Eigenfuhrpark bevorzugt": 1000,
            "Flexibel": 300,
            "Verkauf bevorzugt": 0,
        }.get(dispatch_priority, 300)
        score += priority_points
        reasons.append(f"Dispositionspriorität {dispatch_priority} +{priority_points}")

        days_until_loading = (order.loading_date - planning_day).days
        if days_until_loading < 0:
            score += 60
            reasons.append("Ladetermin bereits überschritten +60")
        elif days_until_loading == 0:
            score += 45
            reasons.append("Ladung heute +45")
        elif days_until_loading == 1:
            score += 30
            reasons.append("Ladung morgen +30")
        else:
            score += max(0, 15 - days_until_loading)
            reasons.append(f"Ladung in {days_until_loading} Tagen")

        if order.loading_time_until:
            score += 20
            reasons.append("festes Ladezeitfenster +20")
        if order.unloading_time_until:
            score += 15
            reasons.append("festes Entladezeitfenster +15")

        status = str(getattr(order, "status", "") or "").casefold()
        if status in {"neu", "offen"}:
            score += 5
            reasons.append("offener Auftrag +5")

        required_trailer_types = parse_trailer_types(
            getattr(order, "required_trailer_type", "Plane")
        )
        required_class = (
            VehicleClass.MEGA
            if requires_mega_only(required_trailer_types)
            else VehicleClass.STANDARD
        )
        if required_class is VehicleClass.MEGA:
            score += 10
            reasons.append("Mega erforderlich +10")

        return OrderCandidate(
            order_id=int(order.id),
            order_number=order.order_number,
            priority_score=score,
            priority_reasons=reasons,
            required_vehicle_class=required_class,
            required_trailer_types=required_trailer_types,
        )
