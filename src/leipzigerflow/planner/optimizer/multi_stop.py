from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MultiStopOrder:
    order_id: int
    order_number: str
    loading_location_id: int
    unloading_location_id: int
    loading_window_start: datetime
    loading_window_end: datetime
    unloading_window_start: datetime
    unloading_window_end: datetime
    loading_duration_minutes: int = 60
    unloading_duration_minutes: int = 60


@dataclass(frozen=True, slots=True)
class PlannedOrderStop:
    order_id: int
    order_number: str
    sequence: int
    planned_loading_at: datetime
    planned_unloading_at: datetime
    waiting_minutes: int
    transfer_minutes: int
    transfer_distance_km: float | None
    loaded_drive_minutes: int = 0
    loaded_distance_km: float | None = None
    estimated_route: bool = False


@dataclass(frozen=True, slots=True)
class MultiStopViolation:
    order_id: int
    order_number: str
    message: str


@dataclass(frozen=True, slots=True)
class MultiStopPlan:
    order_ids: tuple[int, ...]
    stops: tuple[PlannedOrderStop, ...]
    feasible: bool
    quality_score: int
    quality_label: str
    total_transfer_minutes: int
    total_drive_minutes: int
    total_distance_km: float | None
    loaded_distance_km: float | None
    empty_distance_km: float | None
    total_waiting_minutes: int
    total_lateness_minutes: int
    estimated_route_legs: int
    violations: tuple[MultiStopViolation, ...] = field(default_factory=tuple)
    explanations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_complete_distance_data(self) -> bool:
        return self.total_distance_km is not None

    @property
    def empty_km_share(self) -> float | None:
        if self.empty_distance_km is None or not self.total_distance_km:
            return None
        return self.empty_distance_km / self.total_distance_km


@dataclass(frozen=True, slots=True)
class MultiStopOptimizationResult:
    current: MultiStopPlan
    optimized: MultiStopPlan
    alternatives: tuple[MultiStopPlan, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        return self.current.order_ids != self.optimized.order_ids

    @property
    def score_improvement(self) -> int:
        return self.optimized.quality_score - self.current.quality_score

    @property
    def distance_saving_km(self) -> float | None:
        if self.current.total_distance_km is None or self.optimized.total_distance_km is None:
            return None
        return self.current.total_distance_km - self.optimized.total_distance_km

    @property
    def time_saving_minutes(self) -> int:
        return self.current.total_drive_minutes - self.optimized.total_drive_minutes
