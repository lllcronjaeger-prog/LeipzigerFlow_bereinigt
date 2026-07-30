from __future__ import annotations

from PySide6.QtCore import Qt
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

from leipzigerflow.imports.driver_excel import DriverImportPreview, build_preview
from leipzigerflow.services.driver_import_service import DriverImportService


class DriverImportDialog(QDialog):
    HEADERS = ["Status", "Excel-Zeile", "MatchCode", "Vorname", "Nachname", "Straße", "PLZ", "Ort", "Telefon", "Hinweis"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = DriverImportService(session)
        self.preview: DriverImportPreview | None = None
        self.setWindowTitle("Fahrer aus Excel importieren")
        self.resize(1180, 720)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Dispoplan-Fahrerdatei auswählen. Unterstützt werden .xls und .xlsx. "
            "MatchCode, Anschrift und Kontakt werden automatisch verarbeitet; alle Fahrer werden aktiv gesetzt."
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
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 170)
        self.table.setColumnWidth(5, 190)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 150)
        self.table.setColumnWidth(8, 150)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Doppelklick auf ein Feld erlaubt Korrekturen vor dem Import."))
        bottom.addStretch()
        self.import_button = QPushButton("Gültige Fahrer importieren")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._import)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.reject)
        bottom.addWidget(self.import_button)
        bottom.addWidget(close_button)
        layout.addLayout(bottom)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Dispoplan-Fahrerdatei auswählen",
            "",
            "Excel-Dateien (*.xls *.xlsx)",
        )
        if not path:
            return
        try:
            preview = self.service.mark_existing(build_preview(path))
        except Exception as exc:
            QMessageBox.critical(self, "Fahrerimport", str(exc))
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
                row.match_code,
                row.first_name,
                row.last_name,
                f"{row.street} {row.house_number}".strip(),
                row.postal_code,
                row.city,
                row.mobile or row.phone,
                "; ".join(row.errors),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (0, 1):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        new_count = sum(row.status == "Neu" for row in self.preview.rows)
        update_count = sum(row.status == "Update" for row in self.preview.rows)
        errors = len(self.preview.error_rows)
        self.summary.setText(
            f"{len(self.preview.rows)} Fahrer gefunden · {new_count} neu · "
            f"{update_count} Aktualisierungen · {errors} Fehler"
        )
        self.import_button.setEnabled(bool(self.preview.valid_rows))

    def _sync_changes(self) -> None:
        assert self.preview is not None
        for index, row in enumerate(self.preview.rows):
            row.match_code = self.table.item(index, 2).text().strip()
            row.first_name = self.table.item(index, 3).text().strip()
            row.last_name = self.table.item(index, 4).text().strip()
            street_value = self.table.item(index, 5).text().strip()
            row.street, row.house_number = self._split_street(street_value)
            row.postal_code = self.table.item(index, 6).text().strip()
            row.city = self.table.item(index, 7).text().strip()
            phone = self.table.item(index, 8).text().strip()
            if row.mobile:
                row.mobile = phone
            else:
                row.phone = phone
            row.errors.clear()
            if not row.match_code:
                row.errors.append("MatchCode fehlt")
            if not row.first_name:
                row.errors.append("Vorname fehlt")
            if not row.last_name:
                row.errors.append("Nachname fehlt")

    @staticmethod
    def _split_street(value: str) -> tuple[str, str]:
        import re
        match = re.match(r"^(.*?)(?:\s+)(\d+[\w\-/]*)$", value)
        return (match.group(1).strip(), match.group(2).strip()) if match else (value, "")

    def _import(self) -> None:
        if self.preview is None:
            return
        self._sync_changes()
        self.service.mark_existing(self.preview)
        if self.preview.error_rows:
            answer = QMessageBox.question(
                self,
                "Fahrerimport",
                f"{len(self.preview.error_rows)} fehlerhafte Zeile(n) werden übersprungen. Fortfahren?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._show_preview()
                return
        try:
            result = self.service.import_rows(self.preview.rows)
        except Exception as exc:
            QMessageBox.critical(self, "Fahrerimport", f"Import fehlgeschlagen:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Fahrerimport abgeschlossen",
            f"{result.created} Fahrer neu angelegt.\n"
            f"{result.updated} Fahrer aktualisiert.\n"
            f"{result.skipped} Zeilen übersprungen.",
        )
        self.accept()
