from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from leipzigerflow.imports.vehicle_excel import FleetImportPreview, build_preview
from leipzigerflow.services.vehicle_import_service import VehicleImportService


class VehicleImportDialog(QDialog):
    SETTINGS_KEY = "vehicle_import"
    HEADERS = ["Status", "Excel-Zeile", "Kennzeichen KfZ", "Erkannt als", "MatchCode", "Hinweis"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._settings = QSettings("LeipzigerFlow", "VehicleManagement")
        self.service = VehicleImportService(session)
        self.preview: FleetImportPreview | None = None
        self.setWindowTitle("Fahrzeuge aus Excel importieren")
        self.setMinimumSize(900, 620)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Dispoplan-Fahrzeugdatei auswählen. Es wird nur die Spalte „Kennzeichen KfZ“ verarbeitet. "
            "KA-LL bzw. KA LL wird als Zugmaschine erkannt; alle anderen gültigen Kennzeichen als Trailer. "
            "Der MatchCode wird automatisch aus der Endnummer gebildet."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        choose_button = QPushButton("Excel-Datei auswählen …")
        choose_button.clicked.connect(self._choose_file)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(choose_button)
        layout.addLayout(file_row)

        self.summary = QLabel("Noch keine Datei geladen.")
        self.summary.setStyleSheet("font-weight: 600; padding: 6px 0;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 120)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Ungültige Platzhalter und doppelte Kennzeichen werden automatisch übersprungen."))
        bottom.addStretch()
        self.import_button = QPushButton("Gültige Fahrzeuge importieren")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._import)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.reject)
        bottom.addWidget(self.import_button)
        bottom.addWidget(close_button)
        layout.addLayout(bottom)
        self._restore_window_state()


    def _restore_window_state(self) -> None:
        geometry = self._settings.value(f"{self.SETTINGS_KEY}/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            self._ensure_visible_on_screen()
        else:
            self.resize(1180, 760)
        header_state = self._settings.value(f"{self.SETTINGS_KEY}/table_header")
        if isinstance(header_state, QByteArray) and not header_state.isEmpty():
            self.table.horizontalHeader().restoreState(header_state)

    def _ensure_visible_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return
        target = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(self.width(), target.width()), min(self.height(), target.height()))
        self.move(target.center() - self.rect().center())

    def _save_window_state(self) -> None:
        self._settings.setValue(f"{self.SETTINGS_KEY}/geometry", self.saveGeometry())
        self._settings.setValue(f"{self.SETTINGS_KEY}/table_header", self.table.horizontalHeader().saveState())
        self._settings.sync()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self._save_window_state()
        super().closeEvent(event)

    def accept(self) -> None:
        self._save_window_state()
        super().accept()

    def reject(self) -> None:
        self._save_window_state()
        super().reject()

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Dispoplan-Fahrzeugdatei auswählen",
            "",
            "Excel-Dateien (*.xls *.xlsx)",
        )
        if not path:
            return
        try:
            preview = self.service.mark_existing(build_preview(path))
        except Exception as exc:
            QMessageBox.critical(self, "Fahrzeugimport", str(exc))
            return
        self.file_edit.setText(path)
        self.preview = preview
        self._show_preview()

    def _show_preview(self) -> None:
        assert self.preview is not None
        self.table.setRowCount(len(self.preview.rows))
        for row_index, row in enumerate(self.preview.rows):
            values = [
                row.status,
                str(row.source_row),
                row.license_plate,
                row.resource_type,
                row.match_code,
                "; ".join(row.errors),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (0, 1, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        new_count = sum(row.status == "Neu" for row in self.preview.rows)
        update_count = sum(row.status == "Update" for row in self.preview.rows)
        errors = len(self.preview.error_rows)
        self.summary.setText(
            f"{len(self.preview.rows)} Zeilen gefunden · "
            f"{len(self.preview.vehicle_rows)} Zugmaschinen · {len(self.preview.trailer_rows)} Trailer · "
            f"{new_count} neu · {update_count} Aktualisierungen · {errors} Fehler"
        )
        self.import_button.setEnabled(bool(self.preview.valid_rows))

    def _import(self) -> None:
        if self.preview is None:
            return
        if self.preview.error_rows:
            answer = QMessageBox.question(
                self,
                "Fahrzeugimport",
                f"{len(self.preview.error_rows)} fehlerhafte Zeile(n) werden übersprungen. Fortfahren?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            result = self.service.import_rows(self.preview.rows)
        except Exception as exc:
            QMessageBox.critical(self, "Fahrzeugimport", f"Import fehlgeschlagen:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Fahrzeugimport abgeschlossen",
            f"{result.vehicles_created} Zugmaschinen neu angelegt.\n"
            f"{result.vehicles_updated} Zugmaschinen aktualisiert.\n"
            f"{result.trailers_created} Trailer neu angelegt.\n"
            f"{result.trailers_updated} Trailer aktualisiert.\n"
            f"{result.skipped} Zeilen übersprungen.",
        )
        self.accept()
