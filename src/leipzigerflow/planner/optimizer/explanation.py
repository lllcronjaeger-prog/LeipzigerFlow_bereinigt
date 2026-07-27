from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExplanationKind(StrEnum):
    HARD_RULE = "Hard Rule"
    SOFT_RULE = "Soft Rule"
    SYSTEM = "System"


@dataclass(frozen=True, slots=True)
class OptimizationExplanation:
    rule_code: str
    title: str
    message: str
    kind: ExplanationKind
    points: int = 0
    passed: bool = True
