from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RouteLeg:
    distance_km: float | None
    duration_minutes: int
    estimated: bool = False


class RouteProvider(Protocol):
    """Provides a route between two location ids.

    The optimizer stays independent from a concrete map provider. A future
    Dispoplan or routing adapter can implement this protocol without changing
    the optimization core.
    """

    def route(self, origin_location_id: int, destination_location_id: int) -> RouteLeg:
        ...


class MatrixRouteProvider:
    """Deterministic route provider backed by an in-memory matrix."""

    def __init__(
        self,
        matrix: dict[tuple[int, int], RouteLeg | tuple[float | None, int]],
        *,
        default_duration_minutes: int = 60,
    ) -> None:
        self._matrix: dict[tuple[int, int], RouteLeg] = {}
        self.default_duration_minutes = max(0, int(default_duration_minutes))
        for key, value in matrix.items():
            if isinstance(value, RouteLeg):
                self._matrix[key] = value
            else:
                distance, duration = value
                self._matrix[key] = RouteLeg(distance, int(duration), estimated=False)

    def route(self, origin_location_id: int, destination_location_id: int) -> RouteLeg:
        if origin_location_id == destination_location_id:
            return RouteLeg(0.0, 0, estimated=False)
        direct = self._matrix.get((origin_location_id, destination_location_id))
        if direct is not None:
            return direct
        reverse = self._matrix.get((destination_location_id, origin_location_id))
        if reverse is not None:
            return reverse
        return RouteLeg(None, self.default_duration_minutes, estimated=True)


class ConservativeRouteProvider:
    """Safe fallback used until real routing data is connected.

    It never invents kilometres. Different locations receive a configurable
    conservative transfer duration so time-window checks remain useful.
    """

    def __init__(self, default_duration_minutes: int = 60) -> None:
        self.default_duration_minutes = max(0, int(default_duration_minutes))

    def route(self, origin_location_id: int, destination_location_id: int) -> RouteLeg:
        if origin_location_id == destination_location_id:
            return RouteLeg(0.0, 0, estimated=False)
        return RouteLeg(None, self.default_duration_minutes, estimated=True)
