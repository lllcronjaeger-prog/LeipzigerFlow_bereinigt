from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class RouteResult:
    distance_km: float | None
    duration_minutes: int
    toll_km: float = 0.0
    countries: tuple[str, ...] = ()
    provider: str = "fallback"
    from_cache: bool = False
    estimated: bool = False
    warning: str = ""
