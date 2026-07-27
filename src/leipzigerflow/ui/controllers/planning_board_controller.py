from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer
from sqlalchemy.orm import Session

from leipzigerflow.services.planning_board_move_service import PlanningBoardMoveService
from leipzigerflow.ui.dragdrop import MoveOperation, OrderDragPayload


class PlanningBoardController(QObject):
    """Koordiniert Verschieben und verzögerten UI-Refresh sicher über den Qt-Eventloop."""

    def __init__(
        self,
        session: Session,
        refresh_callback: Callable[[], None],
        select_tour_callback: Callable[[int], None],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._move_service = PlanningBoardMoveService(session)
        self._refresh_callback = refresh_callback
        self._select_tour_callback = select_tour_callback
        self._refresh_pending = False

    def move_to_tour(self, operation: MoveOperation, open_orders) -> int:
        target_id = self._move_service.move_to_tour(operation, open_orders)
        self.request_refresh(target_id)
        return target_id

    def move_to_open(self, payload: OrderDragPayload) -> None:
        self._move_service.move_to_open(payload)
        self.request_refresh()

    def request_refresh(self, selected_tour_id: int | None = None) -> None:
        """Fasst Refresh-Anforderungen zusammen und führt sie nach dem aktuellen Event aus."""
        if self._refresh_pending:
            return
        self._refresh_pending = True

        def perform_refresh() -> None:
            self._refresh_pending = False
            self._refresh_callback()
            if selected_tour_id is not None:
                self._select_tour_callback(selected_tour_id)

        QTimer.singleShot(0, perform_refresh)
