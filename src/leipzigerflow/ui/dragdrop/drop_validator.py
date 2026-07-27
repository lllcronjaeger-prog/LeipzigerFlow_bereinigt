from __future__ import annotations

from dataclasses import dataclass

from .mime_types import OrderDragPayload


@dataclass(frozen=True, slots=True)
class DropValidation:
    allowed: bool
    message: str = ""
    same_tour: bool = False


def validate_tour_drop(payload: OrderDragPayload | None, target_tour) -> DropValidation:
    if payload is None or not payload.order_ids:
        return DropValidation(False, "Keine gültigen Aufträge im Ziehvorgang.")
    if target_tour is None:
        return DropValidation(False, "Bitte eine Tourkarte als Ziel wählen.")
    if getattr(target_tour, "planning_locked", False):
        return DropValidation(False, "Die Zieltour ist fixiert.")
    source_id = payload.source_tour_id
    same_tour = source_id is not None and int(source_id) == int(target_tour.id)
    if same_tour:
        return DropValidation(False, "Der Auftrag befindet sich bereits in dieser Tour.", True)
    return DropValidation(True)
