from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QMimeData

ORDER_MIME_TYPE = "application/x-leipzigerflow-order-ids"


@dataclass(frozen=True, slots=True)
class OrderDragPayload:
    """Transportiert Aufträge aus der offenen Liste oder aus einer Tour."""

    order_ids: tuple[int, ...]
    source_tour_id: int | None = None

    @property
    def is_tour_transfer(self) -> bool:
        return self.source_tour_id is not None


def encode_order_payload(payload: OrderDragPayload) -> QByteArray:
    data = {
        "order_ids": list(payload.order_ids),
        "source_tour_id": payload.source_tour_id,
    }
    return QByteArray(json.dumps(data).encode("utf-8"))


def decode_order_payload(mime_data: QMimeData) -> OrderDragPayload | None:
    if not mime_data.hasFormat(ORDER_MIME_TYPE):
        return None
    try:
        raw = json.loads(bytes(mime_data.data(ORDER_MIME_TYPE)).decode("utf-8"))
        # Rückwärtskompatibilität zu Sprint 16.3: dort war der Inhalt nur eine ID-Liste.
        if isinstance(raw, list):
            ids = tuple(int(value) for value in raw)
            return OrderDragPayload(ids) if ids else None
        if not isinstance(raw, dict):
            return None
        ids = tuple(int(value) for value in raw.get("order_ids", []))
        if not ids:
            return None
        source = raw.get("source_tour_id")
        return OrderDragPayload(ids, None if source in (None, "") else int(source))
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
