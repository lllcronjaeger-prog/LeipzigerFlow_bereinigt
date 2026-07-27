from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.planner.driving_rules import DrivingRulesEngine
from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.planner.warnings import TourWarningEngine, WarningSeverity
from leipzigerflow.ui.formatters import format_tour_date_span
from leipzigerflow.ui.tour_capacity import calculate_peak_tour_load
from leipzigerflow.ui.tour_utilization import calculate_tour_time_utilization
from leipzigerflow.ui.widgets.tour_timeline import TourTimelineWidget


class TourDetailDialog(QDialog):
    """Eigenständige, frei skalierbare Detailansicht einer Tour.

    Fenstergeometrie und die vom Benutzer gewählte Höhe der horizontalen
    Zeitachse werden dauerhaft gespeichert. Hinweise aus der Plantafel werden
    direkt oberhalb der Zeitachse vollständig erläutert.
    """

    SETTINGS_ORGANIZATION = "LeipzigerFlow"
    SETTINGS_APPLICATION = "TourDetails"

    def __init__(self, tour, parent=None):
        super().__init__(parent)
        self._tour = tour
        self._settings = QSettings(self.SETTINGS_ORGANIZATION, self.SETTINGS_APPLICATION)
        self._settings_key = "tour_detail"

        self.setWindowTitle(f"Tourdetails · {tour.tour_number}")
        self.setObjectName("tour_detail_dialog")
        self.setMinimumSize(860, 480)

        schedule = TimePlanningEngine().build_schedule(tour)
        driving = DrivingRulesEngine().evaluate(tour, schedule)
        warnings = TourWarningEngine().evaluate(tour, planning_date=getattr(tour, "tour_date", None))
        positions = sorted(list(tour.positions), key=lambda p: (p.position or 0, p.id or 0))
        trailer = getattr(tour, "trailer", None) or getattr(getattr(tour, "vehicle", None), "trailer", None)
        trailer_text = getattr(trailer, "display_name", None) or "nicht zugeordnet"
        utilization = calculate_tour_time_utilization(tour, schedule)
        peak_load = calculate_peak_tour_load(positions, schedule.stops)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(10)

        self.detail_splitter = QSplitter(Qt.Orientation.Vertical)
        self.detail_splitter.setObjectName("tour_detail_splitter")
        self.detail_splitter.setChildrenCollapsible(False)
        root.addWidget(self.detail_splitter, 1)

        overview_scroll = QScrollArea()
        overview_scroll.setObjectName("tour_overview_scroll")
        overview_scroll.setWidgetResizable(True)
        overview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        overview_scroll.setMinimumHeight(160)

        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(6, 6, 6, 6)
        overview_layout.setSpacing(10)

        title = QLabel(f"<h2>{tour.tour_number}</h2>")
        title.setObjectName("tourDetailTitle")
        overview_layout.addWidget(title)

        info = QFrame()
        info.setObjectName("panel")
        info_grid = QGridLayout(info)
        info_grid.setContentsMargins(12, 10, 12, 10)
        info_grid.setHorizontalSpacing(18)
        info_grid.setVerticalSpacing(8)
        values = (
            ("Status", tour.status),
            ("Zeitraum", format_tour_date_span(schedule.start_at, schedule.end_at)),
            ("Fahrer", tour.driver_display or "nicht zugeordnet"),
            ("Fahrzeug", tour.vehicle_display or "nicht zugeordnet"),
            ("Trailer", trailer_text),
            ("Aufträge", str(len(positions))),
            ("Arbeitszeit", f"{utilization.work_text} ({utilization.utilization_percent:.0f} % )"),
            ("Lenkzeit", driving.driving_text),
        )
        for index, (caption, value) in enumerate(values):
            row, column = divmod(index, 4)
            label = QLabel(f"<b>{caption}</b><br>{value}")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            info_grid.addWidget(label, row, column)
        overview_layout.addWidget(info)

        utilization_panel = QFrame()
        utilization_panel.setObjectName("panel")
        utilization_layout = QVBoxLayout(utilization_panel)
        utilization_layout.setContentsMargins(12, 10, 12, 10)
        utilization_layout.setSpacing(7)
        utilization_title = QLabel(
            f"<b>⏱ Arbeitszeitauslastung</b> &nbsp; "
            f"{utilization.status_icon} {utilization.status_text}"
        )
        utilization_title.setTextFormat(Qt.TextFormat.RichText)
        utilization_layout.addWidget(utilization_title)
        utilization_bar = QProgressBar()
        utilization_bar.setRange(0, 100)
        utilization_bar.setValue(min(100, max(0, round(utilization.utilization_percent))))
        utilization_bar.setFormat(
            f"{utilization.work_text} · {utilization.utilization_percent:.0f} %"
        )
        utilization_bar.setTextVisible(True)
        utilization_layout.addWidget(utilization_bar)
        utilization_details = QLabel(
            f"<b>Lenkzeit:</b> {utilization.driving_text} &nbsp; · &nbsp; "
            f"<b>Einsatztage:</b> {utilization.deployment_days}<br>"
            f"<span style='color:#64748b'>Laderaumkontrolle: "
            f"{peak_load.weight_kg:,.0f} kg · {peak_load.loading_meters} Lademeter · "
            f"{peak_load.pallets} Paletten · maximal {peak_load.utilization_percent:.0f} %</span>"
        )
        utilization_details.setTextFormat(Qt.TextFormat.RichText)
        utilization_details.setWordWrap(True)
        utilization_layout.addWidget(utilization_details)
        overview_layout.addWidget(utilization_panel)

        overview_layout.addWidget(self._build_warning_panel(warnings))
        overview_layout.addStretch(1)
        overview_scroll.setWidget(overview_page)
        self.detail_splitter.addWidget(overview_scroll)

        timeline_page = QFrame()
        timeline_page.setObjectName("timelinePanel")
        timeline_layout = QVBoxLayout(timeline_page)
        timeline_layout.setContentsMargins(6, 6, 6, 6)
        timeline_layout.setSpacing(6)
        timeline_header = QHBoxLayout()
        timeline_title = QLabel("<h3>Tourablauf</h3>")
        timeline_title.setObjectName("tourTimelineTitle")
        timeline_header.addWidget(timeline_title)
        timeline_header.addStretch(1)
        resize_hint = QLabel("Höhe am Trennbalken mit der Maus anpassen")
        resize_hint.setObjectName("mutedText")
        timeline_header.addWidget(resize_hint)
        timeline_layout.addLayout(timeline_header)

        self.timeline = TourTimelineWidget()
        self.timeline.set_schedule(schedule)
        timeline_layout.addWidget(self.timeline, 1)
        self.detail_splitter.addWidget(timeline_page)

        self.detail_splitter.setStretchFactor(0, 0)
        self.detail_splitter.setStretchFactor(1, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Schließen")
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._restore_ui_state()

    def _build_warning_panel(self, warnings) -> QWidget:
        panel = QFrame()
        panel.setObjectName("tourWarningsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        if not warnings:
            title = QLabel("✓ Keine Hinweise oder Konflikte")
            title.setObjectName("tourWarningsOk")
            layout.addWidget(title)
            return panel

        title = QLabel(f"Hinweise und Konflikte ({len(warnings)})")
        title.setObjectName("tourWarningsTitle")
        layout.addWidget(title)

        severity_meta = {
            WarningSeverity.ERROR: ("⛔", "Kritisch", "warningError"),
            WarningSeverity.WARNING: ("⚠", "Hinweis", "warningWarning"),
            WarningSeverity.INFO: ("ℹ", "Information", "warningInfo"),
        }
        for warning in warnings:
            icon, caption, object_name = severity_meta.get(
                warning.severity,
                ("⚠", "Hinweis", "warningWarning"),
            )
            row = QLabel(f"{icon} <b>{caption}:</b> {warning.message}")
            row.setObjectName(object_name)
            row.setTextFormat(Qt.TextFormat.RichText)
            row.setWordWrap(True)
            layout.addWidget(row)
        return panel

    def _restore_ui_state(self) -> None:
        geometry = self._settings.value(f"{self._settings_key}/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            self._ensure_visible_on_screen()
        else:
            self.resize(1280, 720)

        splitter_state = self._settings.value(f"{self._settings_key}/splitter")
        if isinstance(splitter_state, QByteArray) and not splitter_state.isEmpty():
            self.detail_splitter.restoreState(splitter_state)
        else:
            self.detail_splitter.setSizes([250, 390])

    def _ensure_visible_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return
        target = QGuiApplication.primaryScreen().availableGeometry()
        width = min(max(self.minimumWidth(), self.width()), target.width())
        height = min(max(self.minimumHeight(), self.height()), target.height())
        self.resize(width, height)
        self.move(target.center() - self.rect().center())

    def _save_ui_state(self) -> None:
        self._settings.setValue(f"{self._settings_key}/geometry", self.saveGeometry())
        self._settings.setValue(f"{self._settings_key}/splitter", self.detail_splitter.saveState())
        self._settings.sync()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self._save_ui_state()
        super().closeEvent(event)

    def accept(self) -> None:
        self._save_ui_state()
        super().accept()

    def reject(self) -> None:
        self._save_ui_state()
        super().reject()
