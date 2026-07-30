from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableView, QVBoxLayout
from sqlalchemy import select

from leipzigerflow.database.session import SessionLocal
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.services.location_service import LocationService
from leipzigerflow.ui.dialogs.location_edit_dialog import LocationEditDialog
from leipzigerflow.ui.models.location_table_model import LocationTableModel


class WarehouseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Läger")
        self.resize(1150, 680)
        self.session = SessionLocal()
        self.service = LocationService(self.session)
        self.model = LocationTableModel([])
        self._build_ui()
        self.refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>📦 Läger</h2><p>Neutrale Lade- und Entladestellen ohne feste Kundenzuordnung.</p>"))
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.edit_warehouse)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        new = QPushButton("➕ Neu")
        edit = QPushButton("✏️ Bearbeiten")
        delete = QPushButton("🗑️ Löschen")
        close = QPushButton("Schließen")
        new.clicked.connect(self.new_warehouse)
        edit.clicked.connect(self.edit_warehouse)
        delete.clicked.connect(self.delete_warehouse)
        close.clicked.connect(self.accept)
        for button in (new, edit, delete):
            row.addWidget(button)
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

    def refresh_table(self) -> None:
        locations = list(self.session.scalars(
            select(Location).where(Location.location_type == LocationType.WAREHOUSE).order_by(Location.name)
        ))
        self.model.setLocations(locations)

    def selected(self) -> Location | None:
        indexes = self.table.selectionModel().selectedRows()
        return self.model.location_at(indexes[0].row()) if indexes else None

    def new_warehouse(self) -> None:
        dialog = LocationEditDialog(parent=self)
        index = dialog.cmb_type.findData(LocationType.WAREHOUSE)
        if index >= 0:
            dialog.cmb_type.setCurrentIndex(index)
            dialog.cmb_type.setEnabled(False)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_location_data()
        data["location_type"] = LocationType.WAREHOUSE
        location = Location(**data)
        try:
            self.service.add(location)
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

    def edit_warehouse(self) -> None:
        location = self.selected()
        if location is None:
            return
        dialog = LocationEditDialog(location, self)
        dialog.cmb_type.setEnabled(False)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_location_data()
        data["location_type"] = LocationType.WAREHOUSE
        for key, value in data.items():
            setattr(location, key, value)
        try:
            self.service.update(location)
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

    def delete_warehouse(self) -> None:
        location = self.selected()
        if location is None:
            return
        if QMessageBox.question(self, "Lager löschen", f"Lager '{location.name}' wirklich löschen?") != QMessageBox.StandardButton.Yes:
            return
        self.service.delete(location)
        self.refresh_table()

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
