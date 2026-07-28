from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from PySide6.QtCore import QByteArray, QDate, QMimeData, QPoint, QSettings, QTimer, Signal, Qt
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent, QPixmap
from shiboken6 import isValid

from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDateEdit,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.ui.context_menu import create_context_menu
from leipzigerflow.config.database_config import load_database_config
from leipzigerflow.exports import export_tours
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.planner.period import PlanningPeriod, PlanningPeriodMode
from leipzigerflow.planner.resources import ResourceConflictEngine
from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.planner.driving_rules import DrivingRulesEngine
from leipzigerflow.planner.quality import TourQualityEngine, TourQualityLevel
from leipzigerflow.ui.formatters import format_stop_period, format_tour_date_span
from leipzigerflow.ui.tour_capacity import calculate_peak_tour_load
from leipzigerflow.ui.tour_utilization import calculate_tour_time_utilization
from leipzigerflow.planner.warnings import TourWarningEngine, WarningSeverity
from leipzigerflow.services.tour_service import TourService, TourValidationError
from leipzigerflow.services.transport_order_service import (
    TransportOrderService,
    TransportOrderValidationError,
)
from leipzigerflow.ui.dialogs.tour_planning_dialog import TourPlanningDialog
from leipzigerflow.ui.dialogs.tour_detail_dialog import TourDetailDialog
from leipzigerflow.ui.dialogs.transport_order_edit_dialog import TransportOrderEditDialog
from leipzigerflow.ui.dialogs.dispatch_simulation_dialog import (
    DispatchSimulationDialog,
    MultiDayDispatchSimulationDialog,
)
from leipzigerflow.planner.engine.facade import PlanningEngine
from leipzigerflow.ui.widgets.weekly_planning_board import WeeklyPlanningBoard
from leipzigerflow.ui.widgets.tour_timeline import TourTimelineWidget
from leipzigerflow.ui.widgets.monthly_planning_board import MonthlyPlanningBoard
from leipzigerflow.ui.models.planning_board_models import PlanningOrderTableModel
from leipzigerflow.ui.dragdrop import (
    ORDER_MIME_TYPE,
    MoveOperation,
    OrderDragPayload,
    decode_order_payload,
    encode_order_payload,
    validate_tour_drop,
)


class TourCardListWidget(QListWidget):
    """Drop-Liste für Tourkarten mit stabilem Rand-Autoscroll."""

    ordersDropped = Signal(object, int)
    AUTO_SCROLL_MARGIN = 72
    AUTO_SCROLL_INTERVAL_MS = 35
    AUTO_SCROLL_MAX_STEP = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tourCardList")
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSpacing(8)
        self.setUniformItemSizes(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAutoScroll(False)  # eigener, kontrollierter Autoscroll
        self._drag_position = None
        self._drag_payload = None
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(self.AUTO_SCROLL_INTERVAL_MS)
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)

    def dragEnterEvent(self, event: QDragEnterEvent):
        payload = decode_order_payload(event.mimeData())
        if payload is not None:
            self._drag_payload = payload
            self._drag_position = event.position().toPoint()
            self._auto_scroll_timer.start()
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        payload = decode_order_payload(event.mimeData())
        if payload is not None:
            self._drag_payload = payload
            self._drag_position = event.position().toPoint()
            item = self.itemAt(self._drag_position)
            validation = self._validation_for(item, payload)
            self._highlight_item(item, validation.allowed if item is not None else None)
            if validation.allowed:
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._finish_drag_visuals()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        item = self.itemAt(event.position().toPoint())
        payload = decode_order_payload(event.mimeData())
        validation = self._validation_for(item, payload)
        if item is None or payload is None or not validation.allowed:
            self._finish_drag_visuals()
            event.ignore()
            return

        row = self.row(item)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self._finish_drag_visuals()
        # Erst nach Ende des Qt-Drop-Events darf die Plantafel neu aufgebaut werden.
        QTimer.singleShot(0, lambda p=payload, r=row: self.ordersDropped.emit(p, r))

    def _auto_scroll_tick(self):
        if self._drag_position is None:
            self._auto_scroll_timer.stop()
            return
        viewport_height = self.viewport().height()
        if viewport_height <= 0:
            return
        y = self._drag_position.y()
        margin = min(self.AUTO_SCROLL_MARGIN, max(24, viewport_height // 3))
        delta = 0
        if y < margin:
            ratio = (margin - max(0, y)) / margin
            delta = -max(4, int(self.AUTO_SCROLL_MAX_STEP * ratio))
        elif y > viewport_height - margin:
            ratio = (min(viewport_height, y) - (viewport_height - margin)) / margin
            delta = max(4, int(self.AUTO_SCROLL_MAX_STEP * ratio))
        if delta:
            bar = self.verticalScrollBar()
            old_value = bar.value()
            bar.setValue(old_value + delta)
            if bar.value() != old_value and self._drag_payload is not None:
                item = self.itemAt(self._drag_position)
                validation = self._validation_for(item, self._drag_payload)
                self._highlight_item(item, validation.allowed if item is not None else None)

    def _finish_drag_visuals(self):
        self._auto_scroll_timer.stop()
        self._drag_position = None
        self._drag_payload = None
        self._highlight_item(None)

    def _tour_for_item(self, item):
        if item is None:
            return None
        widget = self.itemWidget(item)
        return getattr(widget, "tour", None)

    def _validation_for(self, item, payload):
        return validate_tour_drop(payload, self._tour_for_item(item))

    def _highlight_item(self, target, allowed: bool | None = None):
        for row in range(self.count()):
            item = self.item(row)
            widget = self.itemWidget(item)
            if widget is not None:
                is_target = item is target
                widget.setProperty("dropTarget", is_target and allowed is True)
                widget.setProperty("dropBlocked", is_target and allowed is False)
                widget.style().unpolish(widget)
                widget.style().polish(widget)


class DraggableOrderLabel(QLabel):
    """Ein einzelner Tourauftrag, der auf eine andere Tour gezogen werden kann."""

    dragStateChanged = Signal(bool)

    def __init__(self, text: str, order_id: int, source_tour_id: int, enabled: bool, parent=None):
        super().__init__(text, parent)
        self.order_id = int(order_id)
        self.source_tour_id = int(source_tour_id)
        self.drag_enabled = bool(enabled)
        self._press_pos = QPoint()
        self.setCursor(
            Qt.CursorShape.OpenHandCursor if self.drag_enabled else Qt.CursorShape.ForbiddenCursor
        )
        self.setToolTip(
            "Auftrag auf eine andere Tour ziehen"
            if self.drag_enabled
            else "Die Tour ist fixiert; der Auftrag kann nicht verschoben werden."
        )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.drag_enabled or not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 10:
            return super().mouseMoveEvent(event)

        payload = OrderDragPayload((self.order_id,), self.source_tour_id)
        mime = QMimeData()
        mime.setData(ORDER_MIME_TYPE, encode_order_payload(payload))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.dragStateChanged.emit(True)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            # Während QDrag.exec() läuft, arbeitet Qt in einer verschachtelten
            # Event-Schleife. Periodische Refreshes dürfen die Tourkarte in
            # dieser Zeit nicht löschen. Das Ende wird deshalb immer gemeldet.
            if isValid(self):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                self.dragStateChanged.emit(False)



class OpenOrdersTableView(QTableView):
    """Nimmt Touraufträge auf und setzt sie wieder auf nicht disponiert."""

    ordersReleased = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setProperty("dropTarget", False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        payload = decode_order_payload(event.mimeData())
        if payload is not None and payload.source_tour_id is not None:
            self._set_drop_target(True)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        payload = decode_order_payload(event.mimeData())
        if payload is not None and payload.source_tour_id is not None:
            self._set_drop_target(True)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_target(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        payload = decode_order_payload(event.mimeData())
        if payload is None or payload.source_tour_id is None:
            self._set_drop_target(False)
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self._set_drop_target(False)
        QTimer.singleShot(0, lambda p=payload: self.ordersReleased.emit(p))

    def _set_drop_target(self, active: bool):
        self.setProperty("dropTarget", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)


def attach_vehicle_continuity(tours) -> None:
    """Verknüpft aufeinanderfolgende Touren desselben Fahrzeugs für Leerfahrten."""
    by_vehicle = {}
    ordered = sorted(
        [tour for tour in tours if getattr(tour, "vehicle_id", None)],
        key=lambda item: (item.tour_date, getattr(item, "planned_start_time", None) or datetime.min.time(), item.tour_number),
    )
    engine = TimePlanningEngine()
    for tour in ordered:
        vehicle_id = int(tour.vehicle_id)
        previous = by_vehicle.get(vehicle_id)
        if previous is not None and previous.positions:
            previous_schedule = engine.build_schedule(previous)
            last_position = sorted(previous.positions, key=lambda p: (p.position or 0, p.id or 0))[-1]
            vehicle = getattr(tour, "vehicle", None)
            operation_type = str(getattr(vehicle, "operation_type", "") or "").casefold()
            returns_daily = bool(
                operation_type == "nahverkehr"
                or getattr(vehicle, "daily_return_required", False)
            )
            tour.previous_location = (
                getattr(vehicle, "home_base_location", None)
                if returns_daily
                else last_position.transport_order.unloading_location
            )
            # Ein neuer Arbeitstag beginnt mit einer frischen Schicht. Das Ende
            # der Vortagestour darf deshalb nicht als heutige Arbeitszeit
            # übernommen werden.
            tour.previous_available_at = (
                previous_schedule.end_at
                if previous.tour_date == tour.tour_date
                else None
            )
        else:
            # Die erste sichtbare Tour eines Fahrzeugs beginnt an dessen
            # Heimatbasis. Dadurch erscheint die Leerfahrt zur ersten
            # Ladestelle auch in der vollständigen Tour-/Fahreransicht.
            vehicle = getattr(tour, "vehicle", None)
            tour.previous_location = getattr(vehicle, "home_base_location", None)
            tour.previous_available_at = None
        by_vehicle[vehicle_id] = tour


def empty_run_before_loading(schedule, loading_stop, used_sequences: set[int]):
    """Findet die noch nicht dargestellte Leerfahrt direkt vor einem Ladestopp."""

    candidates = [
        travel for travel in schedule.travels
        if travel.is_empty_run
        and travel.sequence not in used_sequences
        and travel.ended_at <= loading_stop.planned_arrival
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda travel: travel.ended_at)


class TourCard(QFrame):
    """Kompakte Tourübersicht; der vollständige Ablauf erscheint erst nach Auswahl."""

    clicked = Signal()
    activated = Signal()
    dragStateChanged = Signal(bool)

    STATUS_COLORS = {
        "Geplant": "#2563eb",
        "Unterwegs": "#d97706",
        "Abgeschlossen": "#15803d",
        "Erledigt": "#15803d",
        "Storniert": "#b91c1c",
    }

    def __init__(self, tour, warnings, route_plan=None, parent=None):
        super().__init__(parent)
        self.tour = tour
        self.setObjectName("tourCard")
        self.setProperty("statusColor", self.STATUS_COLORS.get(tour.status, "#64748b"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(122)
        self.setMaximumHeight(148)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 10, 0)
        root.setSpacing(10)

        status_bar = QFrame()
        status_bar.setFixedWidth(6)
        status_bar.setStyleSheet(
            f"background-color: {self.STATUS_COLORS.get(tour.status, '#64748b')};"
            "border-top-left-radius: 8px; border-bottom-left-radius: 8px;"
        )
        root.addWidget(status_bar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 7, 0, 7)
        content.setSpacing(3)
        root.addLayout(content, 1)

        header = QHBoxLayout()
        lock_prefix = "🔒 " if getattr(tour, "planning_locked", False) else ""
        title = QLabel(f"{lock_prefix}{tour.tour_number}")
        title.setObjectName("tourTitle")
        header.addWidget(title)
        header.addStretch()
        status = QLabel(tour.status)
        status.setObjectName("statusBadge")
        status.setStyleSheet(
            f"color: {self.STATUS_COLORS.get(tour.status, '#64748b')};"
            "background-color: #f8fafc; border: 1px solid #cbd5e1;"
            "border-radius: 10px; padding: 1px 7px; font-weight: 600;"
        )
        header.addWidget(status)
        content.addLayout(header)

        schedule = TimePlanningEngine().build_schedule(tour)
        driving = DrivingRulesEngine().evaluate(tour, schedule)
        end_text = schedule.end_at.strftime("%H:%M")
        if schedule.end_at.date() != schedule.start_at.date():
            end_text = schedule.end_at.strftime("%d.%m. %H:%M")

        distance_text = "–"
        drive_text = driving.driving_text
        if route_plan is not None:
            if route_plan.total_distance_km is not None:
                distance_text = f"{route_plan.total_distance_km:.1f} km"
            if getattr(route_plan, "total_drive_minutes", None) is not None:
                minutes = int(route_plan.total_drive_minutes)
                drive_text = f"{minutes // 60}:{minutes % 60:02d} h"

        date_span = format_tour_date_span(schedule.start_at, schedule.end_at)
        time_row = QLabel(
            f"📅 {date_span} · {schedule.start_at:%H:%M}–{end_text}"
            f"   ·   📦 {tour.order_count} Auftrag/Aufträge"
            f"   ·   {distance_text} · {drive_text}"
        )
        time_row.setObjectName("tourTime")
        time_row.setTextFormat(Qt.TextFormat.RichText)
        content.addWidget(time_row)

        resources = QLabel(
            f"Fahrer: <b>{tour.driver_display or 'nicht zugeordnet'}</b>"
            f"   ·   Fahrzeug: <b>{tour.vehicle_display or 'nicht zugeordnet'}</b>"
        )
        resources.setObjectName("resourceLabel")
        resources.setTextFormat(Qt.TextFormat.RichText)
        content.addWidget(resources)

        utilization = calculate_tour_time_utilization(tour, schedule)
        utilization_row = QHBoxLayout()
        utilization_row.setSpacing(8)
        utilization_label = QLabel(f"⏱ Arbeitszeit {utilization.work_text}")
        utilization_label.setObjectName("tourUtilizationLabel")
        utilization_row.addWidget(utilization_label)
        utilization_bar = QProgressBar()
        utilization_bar.setObjectName("tourUtilizationBar")
        utilization_bar.setRange(0, 100)
        utilization_bar.setValue(min(100, max(0, round(utilization.utilization_percent))))
        utilization_bar.setTextVisible(False)
        utilization_bar.setFixedHeight(10)
        utilization_bar.setToolTip(
            f"{utilization.status_icon} {utilization.status_text}: "
            f"{utilization.work_text} ({utilization.utilization_percent:.0f} %)"
        )
        utilization_row.addWidget(utilization_bar, 1)
        utilization_status = QLabel(
            f"{utilization.status_icon} {utilization.utilization_percent:.0f} %"
        )
        utilization_status.setObjectName("tourUtilizationStatus")
        utilization_row.addWidget(utilization_status)
        content.addLayout(utilization_row)

        if warnings:
            warning_count = len(warnings)
            warning_label = QLabel(f"⚠ {warning_count} Hinweis(e)")
            warning_label.setObjectName("warningLabel")
            content.addWidget(warning_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        event.accept()
        QTimer.singleShot(0, self.activated.emit)


class TourDetailPanel(QFrame):
    """Kompakte Detailansicht für die aktuell markierte Tour."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tourDetailPanel")
        self.setMinimumHeight(195)
        self.setMaximumHeight(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        self.title = QLabel("Tourdetails")
        self.title.setObjectName("detailTitle")
        layout.addWidget(self.title)
        self.content = QLabel("Eine Tour auswählen, um Details anzuzeigen.")
        self.content.setObjectName("detailContent")
        self.content.setWordWrap(True)
        self.content.setTextFormat(Qt.TextFormat.RichText)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.setMaximumHeight(54)
        layout.addWidget(self.content)
        timeline_title = QLabel("Tourablauf")
        timeline_title.setObjectName("detailTitle")
        layout.addWidget(timeline_title)
        self.timeline = TourTimelineWidget()
        layout.addWidget(self.timeline, 1)

    def show_tour(self, tour):
        if tour is None:
            self.title.setText("Tourdetails")
            self.content.setText("Eine Tour auswählen, um Details anzuzeigen.")
            self.timeline.set_schedule(type("EmptySchedule", (), {"stops": [], "travels": [], "breaks": []})())
            return
        schedule = TimePlanningEngine().build_schedule(tour)
        driving = DrivingRulesEngine().evaluate(tour, schedule)
        positions = sorted(list(tour.positions), key=lambda p: (p.position or 0, p.id or 0))
        trailer = getattr(tour, "trailer", None) or getattr(getattr(tour, "vehicle", None), "trailer", None)
        if trailer is not None:
            trailer_number = str(getattr(trailer, "trailer_number", "") or "").strip()
            trailer_plate = str(getattr(trailer, "license_plate", "") or "").strip()
            trailer_type = str(getattr(trailer, "trailer_type", "") or "").strip()
            trailer_text = " – ".join(value for value in (trailer_number, trailer_plate, trailer_type) if value)
        else:
            trailer_text = "nicht zugeordnet"

        vehicle_class = str(getattr(getattr(tour, "vehicle", None), "vehicle_class", "") or "")
        vehicle_text = tour.vehicle_display or "nicht zugeordnet"
        if vehicle_class and tour.vehicle_display:
            vehicle_text = f"{vehicle_text} ({vehicle_class})"

        utilization = calculate_tour_time_utilization(tour, schedule)
        self.title.setText(str(tour.tour_number))
        self.content.setText(
            f"<b>Status:</b> {tour.status} &nbsp; · &nbsp; "
            f"<b>Zeitraum:</b> {format_tour_date_span(schedule.start_at, schedule.end_at)} &nbsp; · &nbsp; "
            f"<b>Fahrer:</b> {tour.driver_display or 'nicht zugeordnet'} &nbsp; · &nbsp; "
            f"<b>Fahrzeug:</b> {vehicle_text}<br>"
            f"<b>Trailer:</b> {trailer_text} &nbsp; · &nbsp; "
            f"<b>Lenkzeit:</b> {driving.driving_text} &nbsp; · &nbsp; "
            f"<b>Arbeitszeit:</b> {utilization.work_text} ({utilization.utilization_percent:.0f} %) &nbsp; · &nbsp; "
            f"<b>Lenkzeit:</b> {driving.driving_text} &nbsp; · &nbsp; "
            f"<b>Aufträge:</b> {len(positions)}"
        )
        self.timeline.set_schedule(schedule)


class PlanningBoardDialog(QDialog):
    """Professionelle Tagesplantafel mit Tourkarten und direkter Disposition."""

    REFRESH_INTERVAL_MS = max(1, load_database_config().refresh_seconds) * 1000

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.tour_service = TourService(session)
        self.order_service = TransportOrderService(session)
        self.warning_engine = TourWarningEngine()
        self.resource_conflict_engine = ResourceConflictEngine()
        self.time_planning_engine = TimePlanningEngine()
        self.period_mode = PlanningPeriodMode.DAY
        self._weekly_selected_tour_id = None
        self._monthly_selected_tour_id = None
        self._all_orders = []
        self._tours = []
        self._settings = QSettings("LeipzigerFlow", "Plantafel")
        self._closing = False

        self.setWindowTitle("Plantafel Professional · Sprint 16.4.2")
        self.resize(1640, 940)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(12)
        root.addLayout(self._build_header())
        root.addLayout(self._build_date_bar())
        root.addLayout(self._build_filter_bar())
        root.addLayout(self._build_metrics())

        self.work_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.work_splitter.addWidget(self._build_tour_area())
        self.work_splitter.addWidget(self._build_order_area())
        self.work_splitter.setSizes([820, 760])
        self.work_splitter.setStretchFactor(0, 1)
        self.work_splitter.setStretchFactor(1, 1)
        root.addWidget(self.work_splitter, 1)

        footer = QHBoxLayout()
        self.summary_label = QLabel()
        footer.addWidget(self.summary_label)
        footer.addStretch()
        self.footer_export_button = QPushButton("Plantafel als Excel exportieren")
        self.footer_export_button.setToolTip(
            "Die aktuell sichtbare Tages-, Wochen- oder Monatsplanung mit Auftragsaufteilung exportieren"
        )
        self.footer_export_button.clicked.connect(self._export_planning_board_excel)
        footer.addWidget(self.footer_export_button)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self._drag_active = False
        self._refresh_pending = False
        self._pending_drop_action = None

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self._periodic_refresh)
        self.refresh_timer.start()
        self._restore_preferences()
        self.refresh()

    def _build_header(self):
        row = QHBoxLayout()
        title = QLabel("Plantafel V2")
        title.setObjectName("pageTitle")
        row.addWidget(title)
        subtitle = QLabel("Tages- und Wochenplanung · Zeitfenster · geplante Stopzeiten")
        subtitle.setObjectName("subtitle")
        row.addWidget(subtitle)
        row.addStretch()
        return row

    def _build_date_bar(self):
        row = QHBoxLayout()
        previous_button = QPushButton("◀ Zurück")
        previous_button.clicked.connect(lambda: self._shift_date(-1))
        row.addWidget(previous_button)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dddd, dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self.refresh)
        self.date_edit.setMinimumWidth(240)
        row.addWidget(self.date_edit)
        next_button = QPushButton("Vor ▶")
        next_button.clicked.connect(lambda: self._shift_date(1))
        row.addWidget(next_button)
        today_button = QPushButton("Heute")
        today_button.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        row.addWidget(today_button)
        row.addSpacing(14)
        self.day_view_button = QPushButton("Tag")
        self.day_view_button.setCheckable(True)
        self.day_view_button.setChecked(True)
        self.day_view_button.clicked.connect(lambda: self._set_period_mode(PlanningPeriodMode.DAY))
        row.addWidget(self.day_view_button)
        self.week_view_button = QPushButton("Woche")
        self.week_view_button.setCheckable(True)
        self.week_view_button.clicked.connect(lambda: self._set_period_mode(PlanningPeriodMode.WEEK))
        row.addWidget(self.week_view_button)
        self.month_view_button = QPushButton("Monat")
        self.month_view_button.setCheckable(True)
        self.month_view_button.clicked.connect(self._set_month_mode)
        row.addWidget(self.month_view_button)
        row.addStretch()
        row.addWidget(QLabel("Planungstage:"))
        self.auto_dispatch_horizon = QSpinBox()
        self.auto_dispatch_horizon.setRange(1, 14)
        self.auto_dispatch_horizon.setValue(3)
        self.auto_dispatch_horizon.setToolTip(
            "Anzahl aufeinanderfolgender Tage, die simuliert und gemeinsam übernommen werden"
        )
        row.addWidget(self.auto_dispatch_horizon)
        auto_dispatch_button = QPushButton("Auto-Disposition simulieren")
        auto_dispatch_button.setToolTip(
            "Offene Ladungen für den gewählten Planungshorizont bewerten"
        )
        auto_dispatch_button.clicked.connect(self._run_dispatch_simulation)
        row.addWidget(auto_dispatch_button)
        refresh_button = QPushButton("Aktualisieren")
        refresh_button.clicked.connect(self.refresh)
        row.addWidget(refresh_button)
        return row


    def _export_planning_board_excel(self):
        """Exportiert exakt die aktuell in der Plantafel sichtbaren Touren."""
        if not self._tours:
            QMessageBox.information(
                self,
                "Plantafel exportieren",
                "Für den gewählten Zeitraum und die aktuellen Filter sind keine Touren sichtbar.",
            )
            return

        selected_date = self.date_edit.date().toPython()
        if self.period_mode == PlanningPeriodMode.WEEK:
            period = PlanningPeriod.week(selected_date)
            default_name = f"Plantafel_KW_{period.start:%Y-%m-%d}_bis_{period.end:%Y-%m-%d}.xlsx"
        elif self.period_mode == "month":
            default_name = f"Plantafel_{selected_date:%Y-%m}.xlsx"
        else:
            default_name = f"Plantafel_{selected_date:%Y-%m-%d}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Plantafel als Excel exportieren",
            default_name,
            "Excel-Arbeitsmappe (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            export_tours(path, self._tours)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Plantafel exportieren",
                f"Die Plantafel konnte nicht exportiert werden:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Plantafel exportiert",
            f"{len(self._tours)} sichtbare Tour(en) wurden exportiert.\n\n{path}",
        )


    def _run_dispatch_simulation(self):
        planning_day = self.date_edit.date().toPython()
        horizon_days = max(1, int(self.auto_dispatch_horizon.value()))
        engine = PlanningEngine(self._session)
        try:
            if horizon_days == 1:
                result, resources, weights = engine.simulate(planning_day)
            else:
                result = engine.simulate_horizon(planning_day, horizon_days=horizon_days)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Automatische Disposition",
                f"Die Simulation konnte nicht erstellt werden:\n{error}",
            )
            return

        if horizon_days == 1:
            dialog = DispatchSimulationDialog(
                result,
                resources,
                weights,
                self,
                apply_callback=lambda selected_result: engine.apply(selected_result, planning_day),
            )
        else:
            dialog = MultiDayDispatchSimulationDialog(
                result,
                self,
                apply_callback=engine.apply_horizon,
            )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _build_filter_bar(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("Plantafelfilter:"))
        self.tour_search_edit = QLineEdit()
        self.tour_search_edit.setClearButtonEnabled(True)
        self.tour_search_edit.setPlaceholderText("Tour, Fahrzeug, Fahrer, Auftrag, Kunde oder Standort suchen …")
        self.tour_search_edit.textChanged.connect(self._filters_changed)
        self.tour_search_edit.setMinimumWidth(330)
        row.addWidget(self.tour_search_edit, 1)
        self.vehicle_filter = QComboBox()
        self.vehicle_filter.addItem("Alle Fahrzeuge", None)
        self.vehicle_filter.currentIndexChanged.connect(self._filters_changed)
        row.addWidget(self.vehicle_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Alle Status", "")
        for status in self.tour_service.STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self._filters_changed)
        row.addWidget(self.status_filter)
        return row

    def _build_metrics(self):
        row = QHBoxLayout()
        self.metric_tours = self._metric_card(row, "Touren")
        self.metric_orders = self._metric_card(row, "Ungeplant")
        self.metric_active = self._metric_card(row, "Unterwegs")
        self.metric_warnings = self._metric_card(row, "Warnungen")
        return row

    @staticmethod
    def _metric_card(layout, caption):
        frame = QFrame()
        frame.setObjectName("metricCard")
        card_layout = QVBoxLayout(frame)
        value = QLabel("0")
        value.setObjectName("metricValue")
        label = QLabel(caption)
        label.setObjectName("metricLabel")
        card_layout.addWidget(value)
        card_layout.addWidget(label)
        layout.addWidget(frame, 1)
        return value

    def _build_tour_area(self):
        widget = QFrame()
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h3>Touren des Tages</h3>"))
        hint = QLabel("Aufträge rechts auswählen und auf die gewünschte Tourkarte ziehen.")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        self.tour_stack = QStackedWidget()
        self.tour_list = TourCardListWidget()
        self.tour_list.itemDoubleClicked.connect(lambda *_: self._open_selected_tour_details())
        self.tour_list.currentItemChanged.connect(lambda *_: self._on_tour_selection_changed())
        self.tour_list.itemSelectionChanged.connect(self._on_tour_selection_changed)
        self.tour_list.ordersDropped.connect(self._drop_orders_on_tour)
        self.tour_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tour_list.customContextMenuRequested.connect(self._show_tour_context_menu)
        self.weekly_board = WeeklyPlanningBoard()
        self.weekly_board.tourActivated.connect(self._activate_weekly_tour)
        self.weekly_board.tourOpenRequested.connect(self._open_weekly_tour)
        self.tour_stack.addWidget(self.tour_list)
        self.tour_stack.addWidget(self.weekly_board)
        self.monthly_board = MonthlyPlanningBoard()
        self.monthly_board.dayRequested.connect(self._open_month_day)
        self.tour_stack.addWidget(self.monthly_board)
        layout.addWidget(self.tour_stack, 1)
        self.selection_summary_label = QLabel("Keine Tour ausgewählt")
        self.selection_summary_label.setObjectName("hint")
        layout.addWidget(self.selection_summary_label)
        button_row = QHBoxLayout()
        detail_button = QPushButton("Tour öffnen")
        detail_button.clicked.connect(self._open_selected_tour_details)
        button_row.addWidget(detail_button)
        open_button = QPushButton("Tour disponieren")
        open_button.clicked.connect(self._open_selected_tour)
        button_row.addWidget(open_button)
        planned_button = QPushButton("Geplant")
        planned_button.setToolTip("Ausgewählte Tour und ihre Aufträge auf Geplant setzen")
        planned_button.clicked.connect(lambda: self._change_selected_tour_status("Geplant"))
        button_row.addWidget(planned_button)
        underway_button = QPushButton("Unterwegs")
        underway_button.setToolTip("Ausgewählte Tour und ihre Aufträge auf Unterwegs setzen")
        underway_button.clicked.connect(lambda: self._change_selected_tour_status("Unterwegs"))
        button_row.addWidget(underway_button)
        complete_button = QPushButton("Abschließen")
        complete_button.setToolTip("Ausgewählte Tour abschließen und ihre Aufträge erledigen")
        complete_button.clicked.connect(lambda: self._change_selected_tour_status("Abgeschlossen"))
        button_row.addWidget(complete_button)
        button_row.addStretch()
        layout.addLayout(button_row)
        return widget

    def _build_order_area(self):
        widget = QFrame()
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h3>Nicht disponierte Aufträge</h3>"))
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Auftragsnummer, Kunde, Standort oder Text suchen …")
        self.search_edit.textChanged.connect(self._filter_orders)
        layout.addWidget(self.search_edit)
        self.order_model = PlanningOrderTableModel()
        self.order_table = OpenOrdersTableView()
        self._configure_table(self.order_table, self.order_model)
        self.order_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.order_table.setDragEnabled(True)
        self.order_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.order_table.doubleClicked.connect(self._edit_selected_order)
        self.order_table.ordersReleased.connect(self._release_orders_to_open)
        layout.addWidget(self.order_table, 1)
        button_row = QHBoxLayout()
        edit_button = QPushButton("Auftrag bearbeiten")
        edit_button.clicked.connect(self._edit_selected_order)
        button_row.addWidget(edit_button)
        button_row.addStretch()
        self.order_count_label = QLabel()
        button_row.addWidget(self.order_count_label)
        layout.addLayout(button_row)
        return widget

    @staticmethod
    def _configure_table(table, model):
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.horizontalHeader().setStretchLastSection(True)

    def _shift_date(self, days: int):
        if self.period_mode == "month":
            self.date_edit.setDate(self.date_edit.date().addMonths(days))
            return
        step = 7 if self.period_mode == PlanningPeriodMode.WEEK else 1
        self.date_edit.setDate(self.date_edit.date().addDays(days * step))

    def _set_period_mode(self, mode: PlanningPeriodMode):
        self.period_mode = mode
        is_week = mode == PlanningPeriodMode.WEEK
        self.day_view_button.setChecked(not is_week)
        self.week_view_button.setChecked(is_week)
        self.month_view_button.setChecked(False)
        self.tour_stack.setCurrentIndex(1 if is_week else 0)
        self.refresh()


    def _set_month_mode(self):
        self.period_mode = "month"
        self.day_view_button.setChecked(False)
        self.week_view_button.setChecked(False)
        self.month_view_button.setChecked(True)
        self.tour_stack.setCurrentIndex(2)
        self.refresh()

    def _open_month_day(self, selected_date):
        self.date_edit.setDate(QDate(selected_date.year, selected_date.month, selected_date.day))
        self._set_period_mode(PlanningPeriodMode.DAY)

    def _tour_matches_filters(self, tour):
        status = self.status_filter.currentData() if hasattr(self, "status_filter") else ""
        if status and tour.status != status:
            return False
        vehicle_id = self.vehicle_filter.currentData() if hasattr(self, "vehicle_filter") else None
        if vehicle_id and int(tour.vehicle_id or 0) != int(vehicle_id):
            return False
        term = self.tour_search_edit.text().strip().casefold() if hasattr(self, "tour_search_edit") else ""
        if not term:
            return True
        values = [tour.tour_number, tour.status, tour.driver_display, tour.vehicle_display]
        for position in tour.positions:
            order = position.transport_order
            values.extend([order.order_number, getattr(order, "search_text", "")])
        return term in " ".join(str(v or "") for v in values).casefold()

    def _refresh_vehicle_filter(self, tours):
        current = self.vehicle_filter.currentData()
        if current is None:
            saved = self._settings.value("vehicle_id", "", type=str)
            if saved.isdigit():
                current = int(saved)
        vehicles = sorted(
            {(int(t.vehicle_id), t.vehicle_display) for t in tours if t.vehicle_id and t.vehicle_display},
            key=lambda item: item[1],
        )
        blocked = self.vehicle_filter.blockSignals(True)
        self.vehicle_filter.clear()
        self.vehicle_filter.addItem("Alle Fahrzeuge", None)
        for vehicle_id, display in vehicles:
            self.vehicle_filter.addItem(display, vehicle_id)
        index = self.vehicle_filter.findData(current)
        self.vehicle_filter.setCurrentIndex(max(0, index))
        self.vehicle_filter.blockSignals(blocked)

    def _activate_weekly_tour(self, tour_id: int):
        self._weekly_selected_tour_id = int(tour_id)
        self._update_detail_panel()

    def _open_weekly_tour(self, tour_id: int):
        self._weekly_selected_tour_id = int(tour_id)
        self.weekly_board.select_tour(int(tour_id))
        self._open_selected_tour()

    def _periodic_refresh(self):
        """Regelmäßiger Refresh, aber niemals während Drag oder Schließen."""
        if self._closing:
            return
        if self._drag_active:
            self._refresh_pending = True
            return
        self.refresh()

    def _set_drag_active(self, active: bool):
        self._drag_active = bool(active)
        if self._drag_active:
            self.refresh_timer.stop()
            return

        if not self.refresh_timer.isActive():
            self.refresh_timer.start()

        pending_action = self._pending_drop_action
        self._pending_drop_action = None
        if pending_action is not None:
            # Erst nach Rückkehr aus QDrag.exec() Daten und Widgets ändern.
            QTimer.singleShot(0, pending_action)
            return

        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh)

    def refresh(self, *_args):
        if self._closing:
            return
        if self._drag_active:
            self._refresh_pending = True
            return

        selected_tour_id = self._selected_tour_id()
        saved_tour_scroll = self.tour_list.verticalScrollBar().value() if hasattr(self, "tour_list") else 0
        selected_date = self.date_edit.date().toPython()
        if self.period_mode == "month":
            from calendar import monthrange
            start = selected_date.replace(day=1)
            end = selected_date.replace(day=monthrange(selected_date.year, selected_date.month)[1])
            period = type("MonthPeriod", (), {"start": start, "end": end, "contains": lambda self_, d: d is not None and start <= d <= end})()
        else:
            period = PlanningPeriod.week(selected_date) if self.period_mode == PlanningPeriodMode.WEEK else PlanningPeriod.day(selected_date)
        self.tour_service.synchronize_completed_tours()
        all_tours = self.tour_service.get_all()
        attach_vehicle_continuity(all_tours)
        period_tours = [
            tour for tour in all_tours
            if period.contains(self._normalize_date(tour.tour_date))
            and not self.tour_service.is_archived(tour)
        ]
        period_tours.sort(key=lambda item: (item.tour_date, item.tour_number))
        self._refresh_vehicle_filter(period_tours)
        self._tours = [tour for tour in period_tours if self._tour_matches_filters(tour)]

        conflict_messages = self.resource_conflict_engine.messages_by_tour(self._tours)
        if self.period_mode == PlanningPeriodMode.WEEK:
            self.weekly_board.set_data(period.start, self._tours, conflict_messages)
            if selected_tour_id:
                self.weekly_board.select_tour(selected_tour_id)
        elif self.period_mode == "month":
            self.monthly_board.set_data(selected_date, self._tours)
        else:
            self._populate_tour_cards(selected_tour_id, conflict_messages)
            # QListWidget.clear() setzt die Ansicht auf den Anfang zurück.
            # Den vorherigen Scrollstand erst nach dem Layout-Aufbau restaurieren.
            QTimer.singleShot(0, lambda value=saved_tour_scroll: (None if self._closing else self._restore_tour_scroll(value)))

        self._all_orders = [
            order for order in self.tour_service.get_unassigned_orders()
            if order.loading_date == selected_date
        ]
        self._filter_orders()
        self.order_table.resizeColumnsToContents()

        all_warnings = [self.warning_engine.evaluate(tour, planning_date=tour.tour_date) for tour in self._tours]
        active = sum(tour.status == "Unterwegs" for tour in self._tours)
        warning_tour_ids = {
            int(tour.id)
            for tour, warnings in zip(self._tours, all_warnings)
            if warnings or conflict_messages.get(int(tour.id))
        }
        self.metric_tours.setText(str(len(self._tours)))
        self.metric_orders.setText(str(len(self._all_orders)))
        self.metric_active.setText(str(active))
        self.metric_warnings.setText(str(len(warning_tour_ids)))
        period_text = (
            f"Woche {period.start:%d.%m.}–{period.end:%d.%m.%Y}"
            if self.period_mode == PlanningPeriodMode.WEEK
            else (f"Monat {selected_date:%m.%Y}" if self.period_mode == "month" else f"{selected_date:%d.%m.%Y}")
        )
        self.summary_label.setText(
            f"{period_text} · {len(self._tours)} Tour(en) · "
            f"{len(self._all_orders)} nicht disponierte(r) Auftrag/Aufträge am gewählten Tag"
        )
        self._update_detail_panel()

    def _filters_changed(self, *_args):
        self._save_preferences()
        self.refresh()

    def _restore_preferences(self):
        search = self._settings.value("search", "", type=str)
        status = self._settings.value("status", "", type=str)
        self.tour_search_edit.setText(search)
        status_index = self.status_filter.findData(status)
        if status_index >= 0:
            self.status_filter.setCurrentIndex(status_index)
        splitter_state = self._settings.value("work_splitter")
        if isinstance(splitter_state, QByteArray) and not splitter_state.isEmpty():
            self.work_splitter.restoreState(splitter_state)

    def _save_preferences(self):
        self._settings.setValue("search", self.tour_search_edit.text())
        self._settings.setValue("status", self.status_filter.currentData() or "")
        vehicle_id = self.vehicle_filter.currentData()
        self._settings.setValue("vehicle_id", "" if vehicle_id is None else str(vehicle_id))
        self._settings.setValue("work_splitter", self.work_splitter.saveState())

    def _update_detail_panel(self):
        # Tourdetails werden ab Version 18.2 ausschließlich in einem eigenen
        # skalierbaren Fenster dargestellt.
        return

    def _populate_tour_cards(self, selected_tour_id=None, conflict_messages=None):
        self.tour_list.clear()
        selected_date = self.date_edit.date().toPython()
        for row, tour in enumerate(self._tours):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, tour.id)
            warnings = self.warning_engine.evaluate(tour, planning_date=selected_date)
            resource_messages = (conflict_messages or {}).get(int(tour.id), [])
            for message in resource_messages:
                from leipzigerflow.planner.warnings import PlanningWarning
                warnings.append(PlanningWarning("resource_conflict", message, WarningSeverity.ERROR))
            try:
                route_plan = self.tour_service.analyze_multi_stop_tour(tour).current
            except Exception:
                route_plan = None
            card = TourCard(tour, warnings, route_plan=route_plan)
            card.clicked.connect(lambda checked=False, selected_row=row: self._select_tour_row(selected_row))
            card.activated.connect(self._open_selected_tour_details)
            card.dragStateChanged.connect(self._set_drag_active)
            self.tour_list.addItem(item)
            self.tour_list.setItemWidget(item, card)
            card.ensurePolished()
            card.adjustSize()
            size_hint = card.sizeHint()
            size_hint.setHeight(max(size_hint.height(), card.minimumSizeHint().height()))
            item.setSizeHint(size_hint)
            if tour.id == selected_tour_id:
                self.tour_list.setCurrentRow(row)


    def _select_tour_row(self, row: int) -> None:
        """Markiert eine Tour auch bei Klick auf das eingebettete Karten-Widget."""
        if not 0 <= int(row) < self.tour_list.count():
            return
        item = self.tour_list.item(int(row))
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.tour_list.clearSelection()
        item.setSelected(True)
        self.tour_list.setCurrentItem(item)
        self._on_tour_selection_changed()

    def _on_tour_selection_changed(self) -> None:
        """Synchronisiert Auswahlrahmen, Detailansicht und Aktionsstatus."""
        selected_items = list(self.tour_list.selectedItems())
        current_item = self.tour_list.currentItem()
        if current_item is not None and not selected_items:
            current_item.setSelected(True)
            selected_items = [current_item]
        selected_item_ids = {id(item) for item in selected_items}
        for row in range(self.tour_list.count()):
            item = self.tour_list.item(row)
            card = self.tour_list.itemWidget(item)
            if card is None:
                continue
            card.setProperty("selected", id(item) in selected_item_ids or item is current_item)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
        self._update_detail_panel()
        self._update_selection_summary()

    def _filter_orders(self, *_args):
        term = self.search_edit.text().strip().casefold()
        orders = self._all_orders if not term else [
            order for order in self._all_orders if term in order.search_text.casefold()
        ]
        self.order_model.set_orders(orders)
        self.order_count_label.setText(f"{len(orders)} von {len(self._all_orders)}")

    def _drop_orders_on_tour(self, payload: OrderDragPayload, tour_row: int):
        if self._drag_active:
            self._pending_drop_action = lambda p=payload, r=tour_row: self._drop_orders_on_tour(p, r)
            return
        if not 0 <= tour_row < len(self._tours):
            return
        target_id = int(self._tours[tour_row].id)
        operation = MoveOperation(payload.order_ids, payload.source_tour_id, target_id)
        try:
            if operation.source_tour_id is None:
                target_tour = self.tour_service.get(target_id)
                if target_tour is None:
                    raise TourValidationError("Die Zieltour wurde nicht gefunden.")
                by_id = {int(order.id): order for order in self.tour_service.get_unassigned_orders()}
                orders = [by_id[order_id] for order_id in operation.order_ids if order_id in by_id]
                if not orders:
                    raise TourValidationError("Die ausgewählten offenen Aufträge wurden nicht gefunden.")
                target_tour = self.tour_service.add_orders(target_tour, orders)
            else:
                source_tour = self.tour_service.get(operation.source_tour_id)
                target_tour = self.tour_service.get(operation.target_tour_id)
                if source_tour is None or target_tour is None:
                    raise TourValidationError("Quell- oder Zieltour wurde nicht gefunden.")
                target_tour = self.tour_service.transfer_orders(
                    source_tour,
                    target_tour,
                    list(operation.order_ids),
                )
        except TourValidationError as error:
            self._session.rollback()
            QMessageBox.warning(self, "Auftrag konnte nicht verschoben werden", str(error))
            return
        except Exception as error:
            self._session.rollback()
            QMessageBox.critical(
                self,
                "Fehler bei der Disposition",
                f"Die Verschiebung wurde vollständig zurückgerollt.\n\n{error}",
            )
            return
        self._queue_refresh(target_tour.id)

    def _release_orders_to_open(self, payload: OrderDragPayload):
        if self._drag_active:
            self._pending_drop_action = lambda p=payload: self._release_orders_to_open(p)
            return
        if payload.source_tour_id is None:
            return
        try:
            source_tour = self.tour_service.get(int(payload.source_tour_id))
            if source_tour is None:
                raise TourValidationError("Die Quelltour wurde nicht gefunden.")
            self.tour_service.release_orders(source_tour, list(payload.order_ids))
        except TourValidationError as error:
            self._session.rollback()
            QMessageBox.warning(self, "Auftrag konnte nicht freigegeben werden", str(error))
            return
        except Exception as error:
            self._session.rollback()
            QMessageBox.critical(
                self,
                "Fehler bei der Disposition",
                f"Die Freigabe wurde vollständig zurückgerollt.\n\n{error}",
            )
            return
        self._queue_refresh(None)

    def _queue_refresh(self, selected_tour_id: int | None):
        """Refresh erst nach Abschluss sämtlicher Drag-/Mouse-Events."""
        def perform_refresh():
            self.refresh()
            if selected_tour_id is not None:
                self._select_tour(selected_tour_id, ensure_visible=False)
        if self._drag_active:
            self._refresh_pending = True
            return
        QTimer.singleShot(0, perform_refresh)

    def _restore_tour_scroll(self, value: int):
        if self._closing or not hasattr(self, "tour_list") or self._drag_active:
            return
        if not isValid(self.tour_list):
            return
        bar = self.tour_list.verticalScrollBar()
        bar.setValue(max(bar.minimum(), min(int(value), bar.maximum())))

    def _select_tour(self, tour_id: int, ensure_visible: bool = True):
        if self.period_mode == PlanningPeriodMode.WEEK:
            self._weekly_selected_tour_id = int(tour_id)
            self.weekly_board.select_tour(int(tour_id))
            return
        for row, tour in enumerate(self._tours):
            if tour.id == tour_id:
                self.tour_list.setCurrentRow(row)
                if ensure_visible:
                    self.tour_list.scrollToItem(self.tour_list.item(row))
                break

    def _selected_tour_ids(self) -> list[int]:
        if getattr(self, "period_mode", PlanningPeriodMode.DAY) != PlanningPeriodMode.DAY:
            selected = self._selected_tour_id()
            return [selected] if selected else []
        ids = []
        for item in self.tour_list.selectedItems():
            value = item.data(Qt.ItemDataRole.UserRole)
            if value is not None:
                ids.append(int(value))
        return ids

    def _selected_tours(self):
        selected_ids = set(self._selected_tour_ids())
        return [tour for tour in self._tours if int(tour.id) in selected_ids]

    def _update_selection_summary(self):
        if not hasattr(self, "selection_summary_label"):
            return
        tours = self._selected_tours()
        if not tours:
            self.selection_summary_label.setText("Keine Tour ausgewählt")
            return
        orders = sum(len(tour.positions) for tour in tours)
        locked = sum(bool(getattr(tour, "planning_locked", False)) for tour in tours)
        self.selection_summary_label.setText(
            f"{len(tours)} Tour(en) ausgewählt · {orders} Auftrag/Aufträge · {locked} fixiert"
        )

    def _selected_tour_id(self):
        if getattr(self, "period_mode", PlanningPeriodMode.DAY) == PlanningPeriodMode.WEEK:
            return self._weekly_selected_tour_id
        if getattr(self, "period_mode", PlanningPeriodMode.DAY) == "month":
            return self._monthly_selected_tour_id
        item = self.tour_list.currentItem() if hasattr(self, "tour_list") else None
        return int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _selected_tour(self):
        tour_id = self._selected_tour_id()
        return next((tour for tour in self._tours if tour.id == tour_id), None)

    def _selected_order(self):
        rows = self.order_table.selectionModel().selectedRows()
        return self.order_model.order_at(rows[0].row()) if rows else None

    def _show_tour_context_menu(self, position):
        item = self.tour_list.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.tour_list.clearSelection()
            item.setSelected(True)
            self.tour_list.setCurrentItem(item)
        selected = self._selected_tours()
        menu = create_context_menu(self)
        if len(selected) == 1:
            menu.addAction("Tour öffnen", self._open_selected_tour_details)
            planning_menu = menu.addMenu("Planung")
            planning_menu.addAction("Tour disponieren", self._open_selected_tour)
        lock_count = sum(bool(getattr(tour, "planning_locked", False)) for tour in selected)
        menu.addAction(
            f"{len(selected)} Tour(en) fixieren",
            lambda: self._set_selected_tours_locked(True),
        ).setEnabled(lock_count < len(selected))
        menu.addAction(
            "Fixierung aufheben",
            lambda: self._set_selected_tours_locked(False),
        ).setEnabled(lock_count > 0)
        menu.addSeparator()
        status_menu = menu.addMenu("Status ändern")
        for status in self.tour_service.STATUSES:
            label = "Abschließen" if status == "Abgeschlossen" else status
            action = status_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, selected_status=status: self._change_selected_tours_status(selected_status)
            )
        menu.exec(self.tour_list.viewport().mapToGlobal(position))

    def _set_selected_tours_locked(self, locked: bool):
        tours = self._selected_tours()
        if not tours:
            return
        try:
            self.tour_service.set_many_planning_locked(
                [self.tour_service.get(tour.id) for tour in tours if self.tour_service.get(tour.id) is not None],
                locked,
            )
        except TourValidationError as error:
            QMessageBox.warning(self, "Fixierung", str(error))
            return
        self.refresh()

    def _change_selected_tours_status(self, status: str):
        tours = self._selected_tours()
        if not tours:
            return
        try:
            for row_tour in tours:
                tour = self.tour_service.get(row_tour.id)
                if tour is not None:
                    self.tour_service.change_status(tour, status)
        except TourValidationError as error:
            QMessageBox.warning(self, "Status konnte nicht geändert werden", str(error))
            return
        self.refresh()

    def _change_selected_tour_status(self, status: str):
        tour = self._selected_tour()
        if tour is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte zuerst eine Tour auswählen.")
            return
        if status == "Abgeschlossen":
            answer = QMessageBox.question(
                self,
                "Tour abschließen",
                "Die Tour und alle nicht stornierten Aufträge werden als erledigt markiert. Fortfahren?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.tour_service.change_status(tour, status)
        except TourValidationError as error:
            QMessageBox.warning(self, "Status konnte nicht geändert werden", str(error))
            return
        except Exception as error:
            self._session.rollback()
            QMessageBox.critical(self, "Fehler bei der Statusänderung", str(error))
            return
        self.refresh()
        self._select_tour(tour.id)

    def _open_selected_tour_details(self, *_args):
        tour = self._selected_tour()
        if tour is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte eine Tour auswählen.")
            return
        current = self.tour_service.get(int(tour.id)) or tour
        TourDetailDialog(current, parent=self).exec()

    def _open_selected_tour(self, *_args):
        tour = self._selected_tour()
        if tour is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte eine Tour auswählen.")
            return
        dialog = TourPlanningDialog(self.tour_service, tour.id, parent=self)
        dialog.exec()
        self.refresh()

    def _master_data(self):
        customers = list(self._session.scalars(select(Customer).where(Customer.active.is_(True)).order_by(Customer.name)))
        locations = list(self._session.scalars(select(Location).where(Location.active.is_(True)).order_by(Location.name)))
        return customers, locations

    def _edit_selected_order(self, *_args):
        selected = self._selected_order()
        if selected is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte einen Transportauftrag auswählen.")
            return
        order = self.order_service.get(selected.id)
        if order is None:
            self.refresh()
            return
        customers, locations = self._master_data()
        if order.customer and all(item.id != order.customer.id for item in customers):
            customers.append(order.customer)
        for location in (order.loading_location, order.unloading_location):
            if location and all(item.id != location.id for item in locations):
                locations.append(location)
        dialog = TransportOrderEditDialog(customers, locations, order=order, parent=self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.order_service.update(order, dialog.get_transport_order_data())
            except TransportOrderValidationError as error:
                self._session.rollback()
                QMessageBox.warning(self, "Eingabe prüfen", str(error))
                continue
            self.refresh()
            return

    @staticmethod
    def _normalize_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        from datetime import date
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            for candidate in (text, text[:10]):
                try:
                    return date.fromisoformat(candidate)
                except ValueError:
                    continue
        converter = getattr(value, "toPython", None)
        if callable(converter):
            return PlanningBoardDialog._normalize_date(converter())
        return value

    def _shutdown_refresh(self):
        self._closing = True
        timer = getattr(self, "refresh_timer", None)
        if timer is not None and isValid(timer):
            timer.stop()
            try:
                timer.timeout.disconnect(self._periodic_refresh)
            except (RuntimeError, TypeError):
                pass
        self._pending_drop_action = None
        self._refresh_pending = False

    def done(self, result):
        self._shutdown_refresh()
        super().done(result)

    def closeEvent(self, event):
        self._save_preferences()
        self._shutdown_refresh()
        super().closeEvent(event)

    @staticmethod
    def _stylesheet():
        return """
        QDialog { background-color: #f1f5f9; color: #0f172a; }
        QWidget { color: #0f172a; }
        QLabel { color: #0f172a; background-color: transparent; }
        QLabel#pageTitle { font-size: 26px; font-weight: 700; }
        QLabel#subtitle, QLabel#hint, QLabel#metricLabel { color: #64748b; }
        QLabel#metricValue { font-size: 24px; font-weight: 700; }
        QFrame#panel, QFrame#metricCard { background-color: #ffffff; border: 1px solid #dbe3ee; border-radius: 10px; }
        QFrame#metricCard { min-height: 72px; }
        QListWidget#tourCardList { background: transparent; border: none; outline: none; }
        QListWidget#tourCardList::item { background: transparent; border: none; padding: 0; }
        QListWidget#tourCardList::item:selected { background: transparent; }
        QFrame#tourCard { background-color: #ffffff; border: 1px solid #dbe3ee; border-radius: 10px; }
        QFrame#tourCard:hover { background-color:#f8fbff; border:1px solid #60a5fa; }
        QFrame#tourCard[selected="true"] { background-color:#dbeafe; border:3px solid #1d4ed8; }
        QFrame#tourCard[dropTarget="true"] { background-color: #eff6ff; border: 2px solid #2563eb; }
        QFrame#tourCard[dropBlocked="true"] { background-color: #fef2f2; border: 2px solid #dc2626; }
        QLabel#tourTitle { font-size: 17px; font-weight: 700; }
        QLabel#resourceLabel { color: #334155; }
        QLabel#resourceWarning { color: #b45309; }
        QFrame#stopContainer { background-color: #f8fafc; border: 1px solid #eef2f7; border-radius: 6px; }
        QLabel#stopRow { color: #334155; background-color: transparent; padding: 2px 2px 0 2px; }
        QLabel#stopTimeRow { color: #1d4ed8; background-color: transparent; padding: 0 2px 4px 22px; font-size: 12px; }
        QLabel#tourTime, QLabel#weeklyTime { color: #1d4ed8; font-weight: 600; }
        QLabel#emptyStopRow { color: #64748b; background-color: transparent; padding: 2px; font-style: italic; }
        QLabel#tourSummary { color: #475569; font-weight: 600; }
        QFrame#weekDayColumn, QFrame#weekDayColumnToday { background:#f8fafc; border:1px solid #dbe3ee; border-radius:8px; }
        QFrame#weekDayColumnToday { border:2px solid #3b82f6; background:#eff6ff; }
        QFrame#compactTourRow { background:#ffffff; border:1px solid #cbd5e1; border-radius:7px; }
        QFrame#compactTourRow:hover { border:1px solid #60a5fa; background:#f8fbff; }
        QFrame#compactTourRow[selected="true"] { border:2px solid #2563eb; background:#eff6ff; }
        QLabel#compactResources { color:#334155; }
        QLabel#compactWarning { color:#9a3412; font-size:11px; }
        QListWidget#dayTourList { background:transparent; border:none; }
        QListWidget#dayTourList::item { background:transparent; border:none; }
        QPushButton#monthDay { text-align:left; padding:8px; background:#ffffff; border:1px solid #dbe3ee; border-radius:7px; }
        QPushButton#monthDay:hover { border:2px solid #2563eb; background:#eff6ff; }
        QPushButton#monthDayOutside { background:#f1f5f9; color:#94a3b8; }
        QLabel#warningLabel { color: #9a3412; background-color: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; padding: 5px; }
        QPushButton { color: #0f172a; background-color: #ffffff; padding: 7px 13px; border: 1px solid #cbd5e1; border-radius: 6px; }
        QPushButton:hover { background-color: #e2e8f0; }
        QPushButton:pressed { background-color: #cbd5e1; }
        QPushButton:checked { color: #ffffff; background-color: #2563eb; border-color: #1d4ed8; font-weight: 700; }
        QLineEdit, QComboBox, QDateEdit { color: #0f172a; background-color: #ffffff; selection-color: #ffffff; selection-background-color: #2563eb; padding: 7px; border: 1px solid #cbd5e1; border-radius: 6px; }
        QComboBox QAbstractItemView, QDateEdit QAbstractItemView { color: #0f172a; background-color: #ffffff; selection-color: #ffffff; selection-background-color: #2563eb; }
        QComboBox::drop-down { border: none; width: 26px; }
        QComboBox::down-arrow { width: 10px; height: 10px; }
        QComboBox QAbstractItemView::item { color: #0f172a; background-color: #ffffff; min-height: 28px; padding: 4px 8px; }
        QComboBox QAbstractItemView::item:selected { color: #ffffff; background-color: #2563eb; }
        QFrame#tourDetailPanel { background:#ffffff; border:1px solid #dbe3ee; border-radius:10px; }
        QLabel#detailTitle { font-size:18px; font-weight:700; color:#0f172a; }
        QLabel#detailContent { color:#334155; }
        QLabel#timelineDay { color:#0f172a; font-weight:700; padding:6px 2px 2px 2px; }
        QLabel#timelineEmpty { color:#64748b; font-style:italic; }
        QFrame#timelineRow { background:#f8fafc; border:1px solid #e2e8f0; border-radius:7px; }
        QFrame#timelineRow[timelineKind="empty_run"] { background:#fff7ed; border-color:#fed7aa; }
        QFrame#timelineRow[timelineKind="rest"] { background:#f5f3ff; border-color:#ddd6fe; }
        QFrame#timelineRow[timelineKind="waiting"] { background:#fefce8; border-color:#fde68a; }
        QScrollArea#timelineScrollArea { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; }
        QWidget#timelineContainer { background:#f8fafc; }
        QFrame#timelineBlock { background:#ffffff; border:1px solid #cbd5e1; border-radius:8px; }
        QFrame#timelineBlock[timelineKind="loading"] { background:#eff6ff; border-color:#93c5fd; }
        QFrame#timelineBlock[timelineKind="unloading"] { background:#ecfdf5; border-color:#86efac; }
        QFrame#timelineBlock[timelineKind="empty_run"] { background:#fff7ed; border-color:#fdba74; }
        QFrame#timelineBlock[timelineKind="rest"] { background:#f5f3ff; border-color:#c4b5fd; }
        QFrame#timelineBlock[timelineKind="waiting"] { background:#fefce8; border-color:#fde047; }
        QLabel#timelinePeriod { color:#1d4ed8; font-weight:600; }
        QLabel#timelineDetail { color:#64748b; }
        QTableWidget#timelineTable { min-height:150px; }
        QTableView { color: #0f172a; background-color: #ffffff; alternate-background-color: #f8fafc; border: 1px solid #e2e8f0; gridline-color: #e2e8f0; selection-background-color: #dbeafe; selection-color: #0f172a; }
        QTableView[dropTarget="true"] { background-color: #eff6ff; border: 3px solid #2563eb; }
        QTableView::item { color: #0f172a; padding: 4px; }
        QHeaderView::section { color: #0f172a; background-color: #e2e8f0; padding: 8px; border: none; border-right: 1px solid #cbd5e1; font-weight: 600; }
        QSplitter::handle { background-color: transparent; }
        QWidget#weeklyBoard, QScrollArea#weeklyBoardScrollArea, QWidget#weeklyBoardContainer { background: transparent; }
        QScrollBar#weeklyBoardHorizontalScrollBar:horizontal {
            min-height: 18px; max-height: 18px; background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 8px; margin: 0;
        }
        QScrollBar#weeklyBoardHorizontalScrollBar::handle:horizontal {
            background: #64748b; min-width: 60px; border-radius: 7px;
        }
        QScrollBar#weeklyBoardHorizontalScrollBar::handle:horizontal:hover { background: #475569; }
        QScrollBar#weeklyBoardHorizontalScrollBar::add-line:horizontal,
        QScrollBar#weeklyBoardHorizontalScrollBar::sub-line:horizontal { width: 0; }
        QFrame#weekDayColumn { background-color: #f8fafc; border: 1px solid #dbe3ee; border-radius: 9px; }
        QFrame#weekDayColumnToday { background-color: #eff6ff; border: 2px solid #60a5fa; border-radius: 9px; }
        QLabel#weekDayTitle { color: #0f172a; font-size: 14px; font-weight: 700; padding: 5px; }
        QFrame#weeklyTourCard { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; }
        QFrame#weeklyTourCard:hover { border: 1px solid #60a5fa; background-color: #f8fbff; }
        QFrame#weeklyTourCard[selected="true"] { border: 2px solid #2563eb; background-color: #eff6ff; }
        QLabel#weeklyTourTitle { font-weight: 700; font-size: 14px; }
        QLabel#weeklyStop { color: #334155; padding: 1px 0; }
        QLabel#weeklyEmpty, QLabel#emptyWeekDay { color: #64748b; font-style: italic; padding: 10px; }
        QLabel#weeklySummary { color: #475569; font-weight: 600; }
        QLabel#weeklyConflict { color: #991b1b; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 5px; padding: 4px; }
        QToolTip { color: #0f172a; background-color: #ffffff; border: 1px solid #cbd5e1; }
        """
