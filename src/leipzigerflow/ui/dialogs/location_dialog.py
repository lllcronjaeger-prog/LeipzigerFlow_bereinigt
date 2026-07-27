from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from leipzigerflow.database.session import SessionLocal
from leipzigerflow.models.location import Location
from leipzigerflow.services.location_service import (
    LocationService,
)
from leipzigerflow.ui.dialogs.location_edit_dialog import (
    LocationEditDialog,
)
from leipzigerflow.ui.models.location_table_model import (
    LocationTableModel,
)


class LocationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Standortverwaltung")
        self.resize(1100, 650)

        self.session = SessionLocal()
        self.service = LocationService(self.session)

        self.model = LocationTableModel(
            self.service.get_all()
        )

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("<h2>Standorte</h2>")
        layout.addWidget(title)

        self.table = QTableView()
        self.table.setModel(self.model)

        self.table.setAlternatingRowColors(True)

        self.table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )

        self.table.setSortingEnabled(True)

        self.table.doubleClicked.connect(
            self.edit_location
        )

        self.table.horizontalHeader().setStretchLastSection(
            True
        )

        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        self.btn_new = QPushButton("Neu")
        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_delete = QPushButton("Löschen")
        self.btn_close = QPushButton("Schließen")

        self.btn_new.clicked.connect(self.new_location)
        self.btn_edit.clicked.connect(self.edit_location)
        self.btn_delete.clicked.connect(self.delete_location)
        self.btn_close.clicked.connect(self.accept)

        buttons.addWidget(self.btn_new)
        buttons.addWidget(self.btn_edit)
        buttons.addWidget(self.btn_delete)

        buttons.addStretch()

        buttons.addWidget(self.btn_close)

        layout.addLayout(buttons)

    def refresh_table(self):
        self.model.setLocations(
            self.service.get_all()
        )

    def selected_location(self):

        indexes = self.table.selectionModel().selectedRows()

        if not indexes:
            return None

        return self.model.location_at(
            indexes[0].row()
        )

    def new_location(self):

        dialog = LocationEditDialog(parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        location = Location(
            **dialog.get_location_data()
        )

        try:
            self.service.add(location)
            self.refresh_table()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Fehler",
                str(exc),
            )

    def edit_location(self):

        location = self.selected_location()

        if location is None:
            return

        dialog = LocationEditDialog(
            location,
            self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_location_data()

        for key, value in data.items():
            setattr(location, key, value)

        try:
            self.service.update(location)
            self.refresh_table()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Fehler",
                str(exc),
            )

    def delete_location(self):

        location = self.selected_location()

        if location is None:
            return

        answer = QMessageBox.question(
            self,
            "Standort löschen",
            f"Standort '{location.name}' wirklich löschen?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.service.delete(location)
        self.refresh_table()

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)