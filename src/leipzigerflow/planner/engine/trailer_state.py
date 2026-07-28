from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrailerLocationKind(StrEnum):
    """Operational trailer location used by the planning engine.

    A trailer is either coupled to a vehicle or parked at a home base. Customer
    locations are deliberately not part of the valid operational model.
    """

    COUPLED = "Am Fahrzeug"
    BASE = "An Basis"
    UNASSIGNED = "Nicht zugeordnet"
    INVALID_CUSTOMER = "Unzulässiger Kundenstandort"


@dataclass(frozen=True, slots=True)
class TrailerState:
    trailer_id: int | None
    trailer_label: str
    location_kind: TrailerLocationKind
    location_label: str
    coupled_vehicle_id: int | None
    loaded: bool = False

    @property
    def is_operationally_valid(self) -> bool:
        return self.location_kind is not TrailerLocationKind.INVALID_CUSTOMER


@dataclass(frozen=True, slots=True)
class TrailerChangeDecision:
    allowed: bool
    reason: str
    exceptional: bool = False
    penalty_points: int = 0


class BaseTrailerPolicy:
    """Central policy for trailer coupling and changes.

    Rules:
    * trailers stay coupled to their vehicle or at a home base;
    * trailer changes are only allowed at a home base;
    * a loaded trailer change at a base is permitted as an exception and must
      be ranked behind a solution without such a change.
    """

    LOADED_CHANGE_PENALTY = 60
    EMPTY_CHANGE_PENALTY = 12

    def resolve(self, vehicle, trailer) -> TrailerState:
        if trailer is None:
            return TrailerState(
                trailer_id=None,
                trailer_label="",
                location_kind=TrailerLocationKind.UNASSIGNED,
                location_label="",
                coupled_vehicle_id=None,
                loaded=False,
            )

        trailer_id = int(getattr(trailer, "id", 0) or 0) or None
        vehicle_id = int(getattr(vehicle, "id", 0) or 0) or None
        coupled_id = int(getattr(vehicle, "trailer_id", 0) or 0) or None
        label = str(getattr(trailer, "display_name", "") or getattr(trailer, "trailer_number", "") or "")
        location = str(getattr(trailer, "location", "") or "").strip()
        loaded = self._is_loaded(trailer)

        if trailer_id is not None and coupled_id == trailer_id:
            return TrailerState(
                trailer_id=trailer_id,
                trailer_label=label,
                location_kind=TrailerLocationKind.COUPLED,
                location_label=str(getattr(vehicle, "location", "") or location),
                coupled_vehicle_id=vehicle_id,
                loaded=loaded,
            )

        base_labels = self._base_labels(vehicle)
        if location and self._matches_base(location, base_labels):
            kind = TrailerLocationKind.BASE
        elif not location:
            # Existing master data often has no explicit trailer location. An
            # uncoupled trailer is then conservatively treated as being at its
            # vehicle's home base, never at a customer.
            kind = TrailerLocationKind.BASE
            location = next(iter(base_labels), "")
        else:
            kind = TrailerLocationKind.INVALID_CUSTOMER

        return TrailerState(
            trailer_id=trailer_id,
            trailer_label=label,
            location_kind=kind,
            location_label=location,
            coupled_vehicle_id=None,
            loaded=loaded,
        )

    def validate_change(self, *, at_home_base: bool, loaded: bool) -> TrailerChangeDecision:
        if not at_home_base:
            return TrailerChangeDecision(
                allowed=False,
                reason="Trailerwechsel nur an der Heimatbasis zulässig",
            )
        if loaded:
            return TrailerChangeDecision(
                allowed=True,
                reason="Beladener Trailerwechsel an der Basis nur als Ausnahme",
                exceptional=True,
                penalty_points=self.LOADED_CHANGE_PENALTY,
            )
        return TrailerChangeDecision(
            allowed=True,
            reason="Trailerwechsel an der Basis zulässig",
            penalty_points=self.EMPTY_CHANGE_PENALTY,
        )

    @staticmethod
    def _is_loaded(trailer) -> bool:
        status = str(getattr(trailer, "status", "") or "").casefold()
        return any(token in status for token in ("beladen", "geladen", "ladung"))

    @staticmethod
    def _base_labels(vehicle) -> set[str]:
        values = {
            str(getattr(vehicle, "home_base", "") or "").strip(),
            str(getattr(getattr(vehicle, "home_base_location", None), "name", "") or "").strip(),
            str(getattr(getattr(vehicle, "home_base_location", None), "full_display", "") or "").strip(),
        }
        return {value.casefold() for value in values if value}

    @staticmethod
    def _matches_base(location: str, base_labels: set[str]) -> bool:
        normalized = location.casefold()
        return any(base in normalized or normalized in base for base in base_labels)
