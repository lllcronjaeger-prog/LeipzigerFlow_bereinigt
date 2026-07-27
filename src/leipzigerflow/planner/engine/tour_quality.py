from __future__ import annotations

from dataclasses import dataclass, field

from leipzigerflow.planner.engine.models import ProposedAssignment


@dataclass(slots=True)
class TourQualityResult:
    score: int
    reasons: list[str] = field(default_factory=list)
    empty_transfer_minutes: int = 0
    overnight_count: int = 0


class TourQualityEvaluator:
    """Transparent internal quality score used by Planning Engine V3.2."""

    def evaluate(self, assignments: list[ProposedAssignment]) -> TourQualityResult:
        if not assignments:
            return TourQualityResult(score=0, reasons=["Keine Aufträge"])

        ordered = sorted(assignments, key=lambda item: (item.loading_at, item.order_number))
        score = 70
        reasons: list[str] = []
        empty_minutes = sum(max(0, item.transfer_minutes) for item in ordered)
        overnight_count = sum(max(0, item.duty_days - 1) for item in ordered)

        direct_connections = 0
        for previous, current in zip(ordered, ordered[1:]):
            if self._normalize(previous.unloading_location_label) == self._normalize(current.loading_location_label):
                direct_connections += 1

        if direct_connections:
            bonus = min(20, direct_connections * 7)
            score += bonus
            reasons.append(f"{direct_connections} direkte Transportketten-Verbindung(en) +{bonus}")

        if empty_minutes:
            penalty = min(25, empty_minutes // 15)
            score -= penalty
            reasons.append(f"{empty_minutes} Minuten Anfahrt/Leerlauf -{penalty}")
        else:
            score += 8
            reasons.append("Keine erkennbare Leeranfahrt +8")

        if any(item.loading_rebooking_required or item.unloading_rebooking_required for item in ordered):
            score -= 8
            reasons.append("Zeitfensterumbuchung erforderlich -8")
        else:
            score += 5
            reasons.append("Gebuchte Zeitfenster eingehalten +5")

        if overnight_count:
            reasons.append(f"{overnight_count} planmäßige Übernachtung(en) berücksichtigt")

        average_assignment = sum(item.score for item in ordered) / len(ordered)
        if average_assignment >= 250:
            score += 7
            reasons.append("Hohe durchschnittliche Zuordnungsqualität +7")
        elif average_assignment < 100:
            score -= 7
            reasons.append("Niedrige durchschnittliche Zuordnungsqualität -7")

        return TourQualityResult(
            score=max(0, min(100, round(score))),
            reasons=reasons,
            empty_transfer_minutes=empty_minutes,
            overnight_count=overnight_count,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").casefold().split())
