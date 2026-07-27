from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from leipzigerflow.planner.driving_rules import DrivingRulesEngine
from leipzigerflow.planner.quality import TourQualityEngine, TourQualityLevel
from leipzigerflow.planner.time_planning import TimePlanningEngine


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    converter = getattr(value, "toPython", None)
    return _as_date(converter()) if callable(converter) else None


class CompactTourRow(QFrame):
    selected = Signal(int)
    openRequested = Signal(int)

    STATUS_COLORS = {
        "Geplant": "#2563eb", "Unterwegs": "#d97706",
        "Abgeschlossen": "#15803d", "Erledigt": "#15803d",
        "Storniert": "#b91c1c",
    }

    def __init__(self, tour, conflict_messages=None, parent=None):
        super().__init__(parent)
        self.tour_id = int(tour.id)
        self.setObjectName("compactTourRow")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doppelklick: Tour öffnen und bearbeiten")

        schedule = TimePlanningEngine().build_schedule(tour)
        driving = DrivingRulesEngine().evaluate(tour, schedule)
        quality = TourQualityEngine().evaluate(
            schedule_warnings=schedule.warnings,
            driving_issues=driving.issues,
        )
        quality_symbol = {
            TourQualityLevel.GREEN: "●",
            TourQualityLevel.YELLOW: "●",
            TourQualityLevel.RED: "●",
        }[quality.level]
        quality_color = {
            TourQualityLevel.GREEN: "#15803d",
            TourQualityLevel.YELLOW: "#b45309",
            TourQualityLevel.RED: "#b91c1c",
        }[quality.level]

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(2)

        top = QHBoxLayout()
        start = QLabel(f"<b>{schedule.start_at:%H:%M}</b>")
        start.setFixedWidth(42)
        top.addWidget(start)
        title = QLabel(f"<b>{tour.tour_number}</b>")
        top.addWidget(title, 1)
        status = QLabel(str(tour.status))
        status.setStyleSheet(f"color:{self.STATUS_COLORS.get(tour.status, '#64748b')};font-weight:700;")
        top.addWidget(status)
        root.addLayout(top)

        vehicle = tour.vehicle_display or "kein Fahrzeug"
        driver = tour.driver_display or "kein Fahrer"
        resources = QLabel(f"{vehicle} · {driver}")
        resources.setObjectName("compactResources")
        resources.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        root.addWidget(resources)

        bottom = QHBoxLayout()
        quality_label = QLabel(f"{quality_symbol} {quality.label} {quality.score}/100")
        quality_label.setStyleSheet(f"color:{quality_color};font-weight:600;")
        bottom.addWidget(quality_label)
        bottom.addStretch()
        bottom.addWidget(QLabel(f"{tour.order_count} Auftr. · bis {schedule.end_at:%H:%M}"))
        root.addLayout(bottom)

        messages = list(conflict_messages or []) + [
            message for message in schedule.warnings if "überschritten" in message
        ] + [issue.message for issue in driving.issues if issue.severity != "info"]
        if messages:
            warning = QLabel(f"⚠ {messages[0]}")
            warning.setObjectName("compactWarning")
            warning.setToolTip("\n".join(messages))
            root.addWidget(warning)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.tour_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.tour_id)
            self.openRequested.emit(self.tour_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class DayTourList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dayTourList")
        self.setSpacing(4)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)


class WeeklyPlanningBoard(QWidget):
    """Kompakte Wochenansicht für große Tourmengen mit eigenem Scrollbereich pro Tag."""

    tourActivated = Signal(int)
    tourOpenRequested = Signal(int)

    DAY_NAMES = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
    COLUMN_WIDTH = 292

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_tour_id = None
        self._rows = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll_area)

        self.container = QWidget()
        self.columns = QHBoxLayout(self.container)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(8)
        self.scroll_area.setWidget(self.container)

    def set_data(self, week_start, tours, conflicts_by_tour=None):
        week_start = _as_date(week_start)
        if week_start is None:
            return
        while self.columns.count():
            item = self.columns.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        grouped = defaultdict(list)
        for tour in tours:
            tour_day = _as_date(getattr(tour, "tour_date", None))
            if tour_day:
                grouped[tour_day].append(tour)

        conflicts_by_tour = conflicts_by_tour or {}
        self._rows.clear()
        today = date.today()
        viewport_height = max(520, self.scroll_area.viewport().height())

        for offset, name in enumerate(self.DAY_NAMES):
            day = week_start + timedelta(days=offset)
            column = QFrame()
            column.setObjectName("weekDayColumnToday" if day == today else "weekDayColumn")
            column.setFixedWidth(self.COLUMN_WIDTH)
            column.setMinimumHeight(viewport_height - 20)
            layout = QVBoxLayout(column)
            layout.setContentsMargins(7, 7, 7, 7)
            layout.setSpacing(5)

            day_tours = sorted(grouped.get(day, []), key=lambda t: (str(getattr(t, "planned_start_time", "")), t.tour_number))
            title = QLabel(f"<b>{name}</b><br>{day:%d.%m.%Y} · {len(day_tours)} Touren")
            title.setObjectName("weekDayTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)

            day_list = DayTourList()
            for tour in day_tours:
                item = QListWidgetItem()
                row = CompactTourRow(tour, conflicts_by_tour.get(int(tour.id), []))
                row.selected.connect(self._activate)
                row.openRequested.connect(self.tourOpenRequested)
                day_list.addItem(item)
                day_list.setItemWidget(item, row)
                item.setSizeHint(row.sizeHint())
                self._rows[int(tour.id)] = row
            if not day_tours:
                empty_item = QListWidgetItem("Keine Touren")
                empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                day_list.addItem(empty_item)
            layout.addWidget(day_list, 1)
            self.columns.addWidget(column)

        total_width = 7 * self.COLUMN_WIDTH + 6 * self.columns.spacing()
        self.container.resize(total_width, viewport_height)
        self.container.setMinimumSize(total_width, viewport_height)
        if self._selected_tour_id:
            self.select_tour(self._selected_tour_id)

    def _activate(self, tour_id):
        self.select_tour(tour_id)
        self.tourActivated.emit(int(tour_id))

    def select_tour(self, tour_id):
        self._selected_tour_id = int(tour_id)
        for current_id, row in self._rows.items():
            row.set_selected(current_id == self._selected_tour_id)
