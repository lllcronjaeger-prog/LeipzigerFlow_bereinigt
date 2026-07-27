from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MoveOperation:
    """Beschreibt eine Verschiebung; Grundlage für Undo/Redo in Sprint 16.4.3."""

    order_ids: tuple[int, ...]
    source_tour_id: int | None
    target_tour_id: int
