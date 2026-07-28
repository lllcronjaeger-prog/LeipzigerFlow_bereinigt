from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorkdayCalculation:
    empty_run_minutes: int
    waiting_minutes: int
    loading_minutes: int
    driving_minutes: int
    unloading_minutes: int
    return_to_base_minutes: int
    already_planned_minutes: int = 0

    @property
    def assignment_minutes(self) -> int:
        return (
            self.empty_run_minutes
            + self.waiting_minutes
            + self.loading_minutes
            + self.driving_minutes
            + self.unloading_minutes
        )

    @property
    def total_minutes(self) -> int:
        return self.already_planned_minutes + self.assignment_minutes + self.return_to_base_minutes

    def components_text(self) -> str:
        parts = [
            f"Leerfahrt {self.empty_run_minutes} min",
            f"Wartezeit {self.waiting_minutes} min",
            f"Laden {self.loading_minutes} min",
            f"Fahrt {self.driving_minutes} min",
            f"Entladen {self.unloading_minutes} min",
        ]
        if self.return_to_base_minutes:
            parts.append(f"Rückfahrt {self.return_to_base_minutes} min")
        if self.already_planned_minutes:
            parts.insert(0, f"bereits geplant {self.already_planned_minutes} min")
        return ", ".join(parts)


class WorkdayCalculator:
    """Zentrale Arbeitszeitberechnung für Vorschau und Hard Rules.

    Kalenderwartezeiten über Nacht gelten nicht als kontinuierliche Arbeitszeit.
    Fehlende Routingwerte werden deterministisch mit ``fallback_route_minutes``
    ersetzt, damit Scoring und Hard Rules dieselben Werte verwenden.
    """

    def __init__(self, fallback_route_minutes: int = 30):
        self.fallback_route_minutes = max(1, int(fallback_route_minutes))

    def candidate(
        self,
        *,
        score,
        order,
        route_result,
        return_to_base_minutes: int = 0,
        already_planned_minutes: int = 0,
    ) -> WorkdayCalculation:
        route_minutes = self._route_minutes(
            route_result=route_result,
            planned_loading_at=getattr(score, "planned_loading_at", None),
            planned_unloading_at=getattr(score, "planned_unloading_at", None),
        )
        return WorkdayCalculation(
            empty_run_minutes=self._positive(getattr(score, "transfer_minutes", 0)),
            waiting_minutes=self._positive(getattr(score, "waiting_minutes", 0)),
            loading_minutes=self._location_duration(getattr(order, "loading_location", None)),
            driving_minutes=route_minutes,
            unloading_minutes=self._location_duration(getattr(order, "unloading_location", None)),
            return_to_base_minutes=self._positive(return_to_base_minutes),
            already_planned_minutes=self._positive(already_planned_minutes),
        )

    def assignment(self, assignment, order=None) -> WorkdayCalculation:
        route_minutes = self._positive(getattr(assignment, "route_duration_minutes", 0))
        if route_minutes <= 0:
            route_minutes = self.fallback_route_minutes
        return WorkdayCalculation(
            empty_run_minutes=self._positive(getattr(assignment, "transfer_minutes", 0)),
            waiting_minutes=self._positive(getattr(assignment, "waiting_minutes", 0)),
            loading_minutes=self._location_duration(getattr(order, "loading_location", None)),
            driving_minutes=route_minutes,
            unloading_minutes=self._location_duration(getattr(order, "unloading_location", None)),
            return_to_base_minutes=0,
            already_planned_minutes=0,
        )

    def _route_minutes(self, *, route_result, planned_loading_at, planned_unloading_at) -> int:
        route_minutes = self._positive(getattr(route_result, "duration_minutes", 0))
        if route_minutes > 0:
            return route_minutes
        if isinstance(planned_loading_at, datetime) and isinstance(planned_unloading_at, datetime):
            if planned_unloading_at.date() == planned_loading_at.date():
                difference = round((planned_unloading_at - planned_loading_at).total_seconds() / 60)
                if difference > 0:
                    return difference
        return self.fallback_route_minutes

    @staticmethod
    def _location_duration(location) -> int:
        return max(0, int(getattr(location, "loading_duration_minutes", 0) or getattr(location, "unloading_duration_minutes", 0) or 60))

    @staticmethod
    def _positive(value) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
