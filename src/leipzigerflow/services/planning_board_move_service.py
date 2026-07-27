from __future__ import annotations

from sqlalchemy.orm import Session

from leipzigerflow.services.tour_service import TourService, TourValidationError
from leipzigerflow.ui.dragdrop import MoveOperation, OrderDragPayload


class PlanningBoardMoveService:
    """Zentrale, UI-unabhängige Verschiebelogik der Plantafel."""

    def __init__(self, session: Session):
        self._session = session
        self._tour_service = TourService(session)

    def move_to_tour(self, operation: MoveOperation, open_orders) -> int:
        """Verschiebt offene oder bereits disponierte Aufträge auf eine Zieltour."""
        if operation.target_tour_id is None:
            raise TourValidationError("Es wurde keine Zieltour angegeben.")

        target_tour = self._tour_service.get(operation.target_tour_id)
        if target_tour is None:
            raise TourValidationError("Die Zieltour wurde nicht gefunden.")

        try:
            if operation.source_tour_id is None:
                by_id = {int(order.id): order for order in open_orders}
                orders = [by_id[order_id] for order_id in operation.order_ids if order_id in by_id]
                if len(orders) != len(operation.order_ids):
                    raise TourValidationError("Mindestens ein offener Auftrag wurde nicht gefunden.")
                for order in orders:
                    target_tour = self._tour_service.add_order(target_tour, order)
            else:
                source_tour = self._tour_service.get(operation.source_tour_id)
                if source_tour is None:
                    raise TourValidationError("Die Quelltour wurde nicht gefunden.")
                target_tour = self._tour_service.transfer_orders(
                    source_tour,
                    target_tour,
                    list(operation.order_ids),
                )
            return int(target_tour.id)
        except Exception:
            self._session.rollback()
            raise

    def move_to_open(self, payload: OrderDragPayload) -> int | None:
        """Entfernt Aufträge aus einer Tour und stellt sie wieder auf 'Neu'."""
        if payload.source_tour_id is None:
            raise TourValidationError("Nur disponierte Aufträge können nach Offen verschoben werden.")
        source_tour = self._tour_service.get(payload.source_tour_id)
        if source_tour is None:
            raise TourValidationError("Die Quelltour wurde nicht gefunden.")
        try:
            self._tour_service.release_orders(source_tour, list(payload.order_ids))
            return int(source_tour.id)
        except Exception:
            self._session.rollback()
            raise
