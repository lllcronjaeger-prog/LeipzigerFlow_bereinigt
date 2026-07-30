from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from leipzigerflow.models.audit import AuditLog
from leipzigerflow.services.audit_service import AuditService


ENTITY_LABELS = {
    "Customer": "Kunde",
    "Location": "Standort/Lager",
    "TransportOrder": "Transportauftrag",
    "Tour": "Tour",
    "TourPosition": "Tourposition",
    "Driver": "Fahrer",
    "Vehicle": "Zugmaschine",
    "Trailer": "Trailer",
    "WarehouseGroup": "Lagergruppe",
}


class AuditLogDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = AuditService(session)
        self.setWindowTitle("Änderungshistorie")
        self.resize(1350, 720)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>📝 Änderungshistorie</h2>"))

        filters = QHBoxLayout()
        self.user_filter = QLineEdit()
        self.user_filter.setPlaceholderText("Benutzer filtern …")
        self.entity_filter = QComboBox()
        self.entity_filter.addItem("Alle Bereiche", "")
        entity_types = list(self.session.scalars(select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)))
        for entity_type in entity_types:
            self.entity_filter.addItem(ENTITY_LABELS.get(entity_type, entity_type), entity_type)
        refresh = QPushButton("🔄 Aktualisieren")
        refresh.clicked.connect(self.refresh)
        self.user_filter.returnPressed.connect(self.refresh)
        self.entity_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(QLabel("👤"))
        filters.addWidget(self.user_filter, 2)
        filters.addWidget(QLabel("Bereich"))
        filters.addWidget(self.entity_filter, 1)
        filters.addWidget(refresh)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Zeit", "Benutzer", "Quelle", "Bereich", "Datensatz",
            "Aktion", "Feld", "Alter Wert", "Neuer Wert", "Grund",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        rows = self.service.latest(
            limit=1000,
            username=self.user_filter.text(),
            entity_type=self.entity_filter.currentData() or "",
        )
        self.table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            values = [
                entry.occurred_at.strftime("%d.%m.%Y %H:%M:%S"),
                entry.display_name or entry.username or "System",
                entry.source,
                ENTITY_LABELS.get(entry.entity_type, entry.entity_type),
                entry.entity_label or entry.entity_id,
                entry.action,
                entry.field_name,
                entry.old_value,
                entry.new_value,
                entry.reason,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column in (0, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        for column in (7, 8, 9):
            self.table.setColumnWidth(column, min(max(self.table.columnWidth(column), 160), 280))
