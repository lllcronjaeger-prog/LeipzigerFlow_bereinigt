from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from leipzigerflow.config.settings import DATA_DIR


@dataclass(slots=True)
class DispatchRules:
    """Fachliche Grenzen, die unabhängig von Score-Gewichtungen gelten."""

    prefer_mega: bool = False
    max_empty_run_minutes: int = 120
    prefer_regular_driver: bool = True
    max_tour_duration_minutes: int = 10 * 60
    max_daily_work_minutes: int = 10 * 60
    merge_tours: bool = True
    subcontractor_only_if_internal_impossible: bool = True
    minimum_confidence_percent: int = 45
    stability_threshold_points: int = 12
    equivalent_score_margin: int = 10
    planning_horizon_days: int = 7
    sale_distance_threshold_km: float = 130.0
    protect_own_fleet_priority: bool = True
    keep_own_fleet_regional: bool = True
    block_longhaul_sale_for_own_fleet: bool = True

    def validate(self) -> None:
        if self.max_empty_run_minutes < 0:
            raise ValueError("max_empty_run_minutes darf nicht negativ sein")
        if self.max_tour_duration_minutes <= 0:
            raise ValueError("max_tour_duration_minutes muss größer als 0 sein")
        if self.max_daily_work_minutes <= 0:
            raise ValueError("max_daily_work_minutes muss größer als 0 sein")
        if not 0 <= self.minimum_confidence_percent <= 100:
            raise ValueError("minimum_confidence_percent muss zwischen 0 und 100 liegen")
        if self.stability_threshold_points < 0:
            raise ValueError("stability_threshold_points darf nicht negativ sein")
        if self.equivalent_score_margin < 0:
            raise ValueError("equivalent_score_margin darf nicht negativ sein")
        if not 0 <= self.planning_horizon_days <= 31:
            raise ValueError("planning_horizon_days muss zwischen 0 und 31 liegen")
        if self.sale_distance_threshold_km <= 0:
            raise ValueError("sale_distance_threshold_km muss größer als 0 sein")


class DispatchRuleStore:
    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "dispatch_rules.json"

    def load(self) -> DispatchRules:
        if not self.path.exists():
            return DispatchRules()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = DispatchRules.__dataclass_fields__
            values = {key: value for key, value in raw.items() if key in allowed}
            rules = DispatchRules(**values)
            rules.validate()
            return rules
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return DispatchRules()

    def save(self, rules: DispatchRules) -> None:
        rules.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(rules), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
