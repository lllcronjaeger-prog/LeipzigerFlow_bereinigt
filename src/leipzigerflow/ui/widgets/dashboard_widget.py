from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.database.database import SessionLocal
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.services.operations_dashboard import (
    DashboardRecommendation,
    DashboardSnapshot,
    DashboardWarning,
    OperationsDashboardService,
)

TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#5b6472"
BACKGROUND = "#eef1f5"
PANEL_BACKGROUND = "#ffffff"
BORDER = "#d7dde6"
HEADER_BACKGROUND = "#e8edf3"
ROW_ALTERNATE = "#f4f7fa"
SELECTION_BACKGROUND = "#cfe3ff"
SELECTION_TEXT = "#172033"
BUTTON_BACKGROUND = "#e7ebf0"
BUTTON_HOVER = "#d9e0e8"
BUTTON_PRESSED = "#cbd4df"


class DashboardCard(QFrame):
    def __init__(self, title: str, accent: str, callback: Callable[[], None], parent=None):
        super().__init__(parent)
        self._callback = callback
        self._accent = accent
        self.setObjectName("dashboardCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(116)
        self.setStyleSheet(
            f"""
            QFrame#dashboardCard {{ background:{PANEL_BACKGROUND}; border:1px solid {BORDER};
                border-left:6px solid {accent}; border-radius:8px; }}
            QFrame#dashboardCard:hover {{ background:#f8fafc; border:1px solid #aeb8c6;
                border-left:6px solid {accent}; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px; font-weight:600;")
        layout.addWidget(title_label)
        self.value_label = QLabel("0")
        font = QFont()
        font.setPointSize(27)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setStyleSheet(f"color:{TEXT_PRIMARY};")
        layout.addWidget(self.value_label)
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet(f"color:{accent}; font-size:12px; font-weight:600;")
        layout.addWidget(self.detail_label)

    def set_value(self, value: int, detail: str = "") -> None:
        self.value_label.setText(str(value))
        self.detail_label.setText(detail)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
        super().mouseReleaseEvent(event)


class DashboardWidget(QWidget):
    """Live-Arbeitsplatz mit Ressourcen-, Auftrags- und Warnungsübersicht."""

    REFRESH_INTERVAL_MS = 30_000

    def __init__(
        self,
        open_orders: Callable[[], None],
        open_tours: Callable[[], None],
        open_planning_board: Callable[[], None],
        open_drivers: Callable[[], None],
        open_vehicles: Callable[[], None],
        open_trailers: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self._open_orders = open_orders
        self._open_tours = open_tours
        self._open_planning_board = open_planning_board
        self._open_drivers = open_drivers
        self._open_vehicles = open_vehicles
        self._open_trailers = open_trailers
        self._service = OperationsDashboardService()

        self.setObjectName("dashboardRoot")
        self.setStyleSheet(self._style_sheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("dashboardContent")
        scroll.setWidget(content)
        outer.addWidget(scroll)

        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_area = QVBoxLayout()
        title = QLabel("Disponenten-Cockpit")
        title.setObjectName("dashboardTitle")
        title_area.addWidget(title)
        self.date_label = QLabel()
        self.date_label.setObjectName("dashboardDate")
        title_area.addWidget(self.date_label)
        header.addLayout(title_area)
        header.addStretch()
        planning_button = QPushButton("🚛 Auto-Disposition / Plantafel")
        planning_button.clicked.connect(self._open_planning_board)
        header.addWidget(planning_button)
        refresh_button = QPushButton("Jetzt aktualisieren")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)
        root.addLayout(header)

        cockpit = self._create_panel("Heutige Planung")
        cockpit_row = QHBoxLayout()
        self.quality_label = QLabel("Planungsqualität 100 %")
        self.quality_label.setObjectName("qualityLabel")
        cockpit_row.addWidget(self.quality_label)
        self.quality_bar = QProgressBar()
        self.quality_bar.setRange(0, 100)
        self.quality_bar.setTextVisible(False)
        self.quality_bar.setMinimumWidth(260)
        cockpit_row.addWidget(self.quality_bar, 1)
        self.coverage_label = QLabel("Eigenfuhrpark: 0 / 0")
        self.coverage_label.setObjectName("dashboardDate")
        cockpit_row.addWidget(self.coverage_label)
        auto_button = QPushButton("Varianten berechnen")
        auto_button.clicked.connect(self._open_planning_board)
        cockpit_row.addWidget(auto_button)
        cockpit.layout().addLayout(cockpit_row)
        root.addWidget(cockpit)

        resources_title = QLabel("Ressourcen")
        resources_title.setObjectName("sectionTitle")
        root.addWidget(resources_title)
        resources = QGridLayout()
        resources.setSpacing(14)
        self.driver_card = DashboardCard("Verfügbare Fahrer", "#15803d", self._open_drivers)
        self.vehicle_card = DashboardCard("Verfügbare Zugmaschinen", "#2563eb", self._open_vehicles)
        self.trailer_card = DashboardCard("Verfügbare Trailer", "#7c3aed", self._open_trailers)
        for column, card in enumerate((self.driver_card, self.vehicle_card, self.trailer_card)):
            resources.addWidget(card, 0, column)
            resources.setColumnStretch(column, 1)
        root.addLayout(resources)

        planning_title = QLabel("Aufträge und Touren")
        planning_title.setObjectName("sectionTitle")
        root.addWidget(planning_title)
        planning_cards = QGridLayout()
        planning_cards.setSpacing(14)
        self.open_orders_card = DashboardCard("Offene Aufträge", "#2563eb", self._open_orders)
        self.critical_orders_card = DashboardCard("Kritische Aufträge", "#b91c1c", self._open_orders)
        self.tours_today_card = DashboardCard("Touren heute", "#7c3aed", self._open_tours)
        self.underway_card = DashboardCard("Touren unterwegs", "#d97706", self._open_tours)
        self.conflict_card = DashboardCard("Aktive Konflikte", "#b91c1c", self._open_planning_board)
        for column, card in enumerate(
            (self.open_orders_card, self.critical_orders_card, self.tours_today_card, self.underway_card, self.conflict_card)
        ):
            planning_cards.addWidget(card, 0, column)
            planning_cards.setColumnStretch(column, 1)
        root.addLayout(planning_cards)

        middle = QHBoxLayout()
        middle.setSpacing(18)
        warnings_panel = self._create_panel("Warnungen und Handlungsbedarf")
        self.warnings_table = QTableWidget(0, 4)
        self.warnings_table.setHorizontalHeaderLabels(["Priorität", "Bereich", "Betreff", "Hinweis"])
        self._configure_table(self.warnings_table)
        warnings_panel.layout().addWidget(self.warnings_table)
        middle.addWidget(warnings_panel, 1)

        status_panel = self._create_panel("Betriebsstatus")
        self.status_table = QTableWidget(0, 3)
        self.status_table.setHorizontalHeaderLabels(["Bereich", "Kennzahl", "Wert"])
        self._configure_table(self.status_table)
        status_panel.layout().addWidget(self.status_table)
        middle.addWidget(status_panel, 1)
        root.addLayout(middle)

        recommendations_panel = self._create_panel("💡 Empfehlungen des Planungsassistenten")
        self.recommendations_table = QTableWidget(0, 4)
        self.recommendations_table.setHorizontalHeaderLabels(["Status", "Empfehlung", "Begründung", "Aktion"])
        self._configure_table(self.recommendations_table)
        recommendations_panel.layout().addWidget(self.recommendations_table)
        root.addWidget(recommendations_panel)

        lower = QHBoxLayout()
        lower.setSpacing(18)
        tours_panel = self._create_panel("Touren heute")
        self.tours_table = QTableWidget(0, 6)
        self.tours_table.setHorizontalHeaderLabels(
            ["Tour", "Start", "Fahrer", "Zugmaschine", "Trailer", "Status"]
        )
        self._configure_table(self.tours_table)
        self.tours_table.doubleClicked.connect(self._open_tours)
        tours_panel.layout().addWidget(self.tours_table)
        button = QPushButton("Alle Touren öffnen")
        button.clicked.connect(self._open_tours)
        tours_panel.layout().addWidget(button)
        lower.addWidget(tours_panel, 1)

        orders_panel = self._create_panel("Dringende offene Transportaufträge")
        self.orders_table = QTableWidget(0, 6)
        self.orders_table.setHorizontalHeaderLabels(
            ["Auftrag", "Ladedatum", "Kunde", "Von", "Nach", "Status"]
        )
        self._configure_table(self.orders_table)
        self.orders_table.doubleClicked.connect(self._open_orders)
        orders_panel.layout().addWidget(self.orders_table)
        button = QPushButton("Alle Transportaufträge öffnen")
        button.clicked.connect(self._open_orders)
        orders_panel.layout().addWidget(button)
        lower.addWidget(orders_panel, 1)
        root.addLayout(lower)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()
        self.refresh()

    @staticmethod
    def _style_sheet() -> str:
        return f"""
        QWidget#dashboardRoot, QWidget#dashboardContent {{ background:{BACKGROUND}; color:{TEXT_PRIMARY}; }}
        QLabel#dashboardTitle {{ color:#111827; font-size:24px; font-weight:700; }}
        QLabel#dashboardDate {{ color:{TEXT_SECONDARY}; font-size:13px; }}
        QLabel#sectionTitle {{ color:{TEXT_PRIMARY}; font-size:18px; font-weight:700; }}
        QLabel#qualityLabel {{ color:{TEXT_PRIMARY}; font-size:16px; font-weight:700; }}
        QProgressBar {{ background:#e5e7eb; border:1px solid #cbd5e1; border-radius:6px; min-height:14px; }}
        QProgressBar::chunk {{ background:#15803d; border-radius:5px; }}
        QFrame#panel {{ background:{PANEL_BACKGROUND}; border:1px solid {BORDER}; border-radius:8px; }}
        QTableWidget {{ background:{PANEL_BACKGROUND}; alternate-background-color:{ROW_ALTERNATE};
            color:{TEXT_PRIMARY}; border:1px solid #e1e6ed; gridline-color:#e2e7ed;
            selection-background-color:{SELECTION_BACKGROUND}; selection-color:{SELECTION_TEXT}; }}
        QTableWidget::item {{ padding:5px; }}
        QHeaderView::section {{ background:{HEADER_BACKGROUND}; color:{TEXT_PRIMARY}; border:none;
            border-right:1px solid #d6dde6; border-bottom:1px solid #cbd3dd; padding:8px; font-weight:700; }}
        QPushButton {{ background:{BUTTON_BACKGROUND}; color:{TEXT_PRIMARY}; border:1px solid #c3cbd6;
            border-radius:5px; padding:7px 13px; font-weight:600; }}
        QPushButton:hover {{ background:{BUTTON_HOVER}; }}
        QPushButton:pressed {{ background:{BUTTON_PRESSED}; }}
        """

    @staticmethod
    def _create_panel(title: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        return panel

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        header = table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    @staticmethod
    def _item(value: object, centered: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value or ""))
        item.setForeground(QColor(TEXT_PRIMARY))
        if centered:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        today = date.today()
        with SessionLocal() as session:
            snapshot = self._service.build_snapshot(session, today)
        self.date_label.setText(
            f"{today:%d.%m.%Y} · zuletzt aktualisiert {snapshot.generated_at:%H:%M:%S} · automatische Aktualisierung alle 30 Sekunden"
        )
        self._update_cards(snapshot)
        self._fill_warnings(snapshot.warnings[:20])
        self._fill_recommendations(snapshot.recommendations)
        self._fill_status(snapshot)
        self._fill_tours(snapshot.tour_rows)
        self._fill_orders(snapshot.open_order_rows)

    def _update_cards(self, snapshot: DashboardSnapshot) -> None:
        self.driver_card.set_value(snapshot.available_drivers, f"{snapshot.absent_drivers} abwesend")
        self.vehicle_card.set_value(
            snapshot.available_vehicles, f"{snapshot.workshop_vehicles} Werkstatt/Defekt"
        )
        self.trailer_card.set_value(
            snapshot.available_trailers, f"{snapshot.workshop_trailers} Werkstatt/Defekt"
        )
        self.open_orders_card.set_value(
            snapshot.open_orders,
            f"{snapshot.mega_orders} Mega · {snapshot.refrigerated_orders} Kühler",
        )
        self.critical_orders_card.set_value(snapshot.critical_orders, "Ladedatum erreicht/überschritten")
        self.tours_today_card.set_value(snapshot.tours_today, f"{snapshot.incomplete_tours} unvollständig")
        self.underway_card.set_value(snapshot.underway_tours, "aktuell unterwegs")
        self.conflict_card.set_value(snapshot.active_conflicts, "harte Hinweise")
        self.quality_bar.setValue(snapshot.planning_quality)
        self.quality_label.setText(f"Planungsqualität {snapshot.planning_quality} %")
        self.coverage_label.setText(
            f"Eigenfuhrpark heute: {snapshot.own_fleet_planned_today} / {snapshot.own_fleet_orders_today} · "
            f"Verkauf offen: {snapshot.sales_orders_open}"
        )

    def _fill_warnings(self, warnings: list[DashboardWarning]) -> None:
        self.warnings_table.setRowCount(len(warnings))
        labels = {"critical": "Kritisch", "warning": "Bald fällig", "info": "Hinweis"}
        backgrounds = {
            "critical": QColor("#fee2e2"),
            "warning": QColor("#fef3c7"),
            "info": QColor("#e0f2fe"),
        }
        for row, warning in enumerate(warnings):
            values = (labels.get(warning.severity, warning.severity), warning.area, warning.title, warning.detail)
            for column, value in enumerate(values):
                item = self._item(value, centered=column == 0)
                item.setBackground(backgrounds.get(warning.severity, QColor("#ffffff")))
                self.warnings_table.setItem(row, column, item)
        if not warnings:
            self.warnings_table.setRowCount(1)
            item = self._item("Keine aktuellen Warnungen")
            item.setForeground(QColor("#15803d"))
            self.warnings_table.setItem(0, 0, item)
            self.warnings_table.setSpan(0, 0, 1, 4)

    def _fill_recommendations(self, recommendations: list[DashboardRecommendation]) -> None:
        self.recommendations_table.clearSpans()
        if not recommendations:
            self.recommendations_table.setRowCount(1)
            item = self._item("✅ Aktuell keine unmittelbare Optimierung erforderlich")
            item.setForeground(QColor("#15803d"))
            self.recommendations_table.setItem(0, 0, item)
            self.recommendations_table.setSpan(0, 0, 1, 4)
            return
        self.recommendations_table.setRowCount(len(recommendations))
        labels = {"critical": "🔴 Kritisch", "warning": "🟡 Prüfen", "info": "🔵 Hinweis"}
        backgrounds = {
            "critical": QColor("#fee2e2"),
            "warning": QColor("#fef3c7"),
            "info": QColor("#e0f2fe"),
        }
        for row, recommendation in enumerate(recommendations):
            values = (
                labels.get(recommendation.severity, recommendation.severity),
                recommendation.title,
                recommendation.detail,
                recommendation.action,
            )
            for column, value in enumerate(values):
                item = self._item(value, centered=column in (0, 3))
                item.setBackground(backgrounds.get(recommendation.severity, QColor("#ffffff")))
                self.recommendations_table.setItem(row, column, item)

    def _fill_status(self, snapshot: DashboardSnapshot) -> None:
        rows = [
            ("Fahrer", "Aktiv", snapshot.active_drivers),
            ("Fahrer", "Verfügbar", snapshot.available_drivers),
            ("Zugmaschinen", "Aktiv", snapshot.active_vehicles),
            ("Zugmaschinen", "Verfügbar", snapshot.available_vehicles),
            ("Trailer", "Aktiv", snapshot.active_trailers),
            ("Trailer", "Verfügbar", snapshot.available_trailers),
            ("Aufträge", "Offen", snapshot.open_orders),
            ("Touren", "Heute", snapshot.tours_today),
        ]
        self.status_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.status_table.setItem(row, column, self._item(value, centered=column == 2))

    def _fill_tours(self, tours: list[Tour]) -> None:
        self.tours_table.setRowCount(len(tours))
        for row, tour in enumerate(tours):
            trailer = tour.trailer or (tour.vehicle.trailer if tour.vehicle else None)
            values = (
                tour.tour_number,
                tour.planned_start_time.strftime("%H:%M") if tour.planned_start_time else "",
                tour.driver_display or "Offen",
                tour.vehicle_display or "Offen",
                trailer.display_name if trailer else "Offen",
                tour.status,
            )
            for column, value in enumerate(values):
                self.tours_table.setItem(row, column, self._item(value, centered=column in (1, 5)))

    def _fill_orders(self, orders: list[TransportOrder]) -> None:
        self.orders_table.setRowCount(len(orders))
        today = date.today()
        for row, order in enumerate(orders):
            values = (
                order.order_number,
                order.loading_date.strftime("%d.%m.%Y"),
                order.customer.display_name if order.customer else "",
                order.loading_location.full_display if order.loading_location else "",
                order.unloading_location.full_display if order.unloading_location else "",
                order.status,
            )
            for column, value in enumerate(values):
                item = self._item(value, centered=column in (1, 5))
                if order.loading_date <= today:
                    item.setBackground(QColor("#fee2e2"))
                self.orders_table.setItem(row, column, item)
