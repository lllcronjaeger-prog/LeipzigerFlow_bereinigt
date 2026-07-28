from __future__ import annotations

from dataclasses import dataclass, field

from leipzigerflow.planner.engine.score_breakdown import build_score_breakdown


@dataclass(slots=True)
class CandidateDecision:
    order_number: str
    vehicle_label: str
    driver_label: str
    feasible: bool
    score: int
    checks: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    selected: bool = False
    score_components: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_score(cls, score, order_number: str) -> "CandidateDecision":
        return cls(
            order_number=str(order_number),
            vehicle_label=str(getattr(score.resource, "vehicle_label", "")),
            driver_label=str(getattr(score.resource, "driver_label", "")),
            feasible=bool(score.feasible),
            score=int(score.score),
            checks=list(score.reasons),
            rejection_reasons=list(score.rejection_reasons),
            score_components=build_score_breakdown(list(score.reasons), int(score.score)),
        )

    def as_text(self) -> str:
        marker = "GEWÄHLT" if self.selected else ("ZULÄSSIG" if self.feasible else "VERWORFEN")
        details = self.checks if self.feasible else self.rejection_reasons
        component_text = ", ".join(f"{name} {value:+d}" for name, value in self.score_components.items())
        suffix = f" | Teil-Scores: {component_text}" if component_text else ""
        return f"{self.order_number} · {self.vehicle_label}: {marker} ({self.score} Punkte) – " + "; ".join(details) + suffix
