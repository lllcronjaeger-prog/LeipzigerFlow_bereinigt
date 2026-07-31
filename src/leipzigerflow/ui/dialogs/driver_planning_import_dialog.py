from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from leipzigerflow.imports.modulon_resource_planner import ModulonPlanningPreview, build_preview
from leipzigerflow.services.driver_planning_import_service import DriverPlanningImportService
from leipzigerflow.models.driver import Driver
from leipzigerflow.ui.dialogs.modulon_driver_mapping_dialog import ModulonDriverMappingDialog
from sqlalchemy import select


class DriverPlanningImportDialog(QDialog):
    HEADERS = ["Excel-Zeile", "Fahrer-Nr.", "Personal-Nr.", "Fahrer", "Modulon-Gruppe", "Niederlassung", "Datum", "Modulon", "LeipzigerFlow"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = DriverPlanningImportService(session)
        self.preview: ModulonPlanningPreview | None = None
        self.setWindowTitle("Fahrerplanung aus Modulon importieren")
        self.resize(1220, 720)

        root = QVBoxLayout(self)
        info = QLabel(
            "Importiert den monatlichen Modulon-Ressourcenplaner. Belegte Tageszellen werden als "
            "Fahrer-Abwesenheiten gespeichert. Leere Zellen bleiben frei und werden anschließend über das "
            "Arbeitszeitmodell (MO-FR, 2/1 oder 3/1) bewertet. Ein erneuter Monatsimport ersetzt nur die "
            "zuvor aus Modulon importierten Daten dieses Monats."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit(); self.file_edit.setReadOnly(True)
        choose = QPushButton("Modulon-Excel auswählen …"); choose.clicked.connect(self._choose)
        file_row.addWidget(self.file_edit, 1); file_row.addWidget(choose)
        root.addLayout(file_row)

        group_hint = QLabel("Hinweis: Die Spalte ‘Modulon-Gruppe’ ist nur eine Information aus dem Export. Sie ändert keine LeipzigerFlow-Dispositionsgruppe und keine Fahrerzuordnung.")
        group_hint.setWordWrap(True)
        group_hint.setObjectName("mutedText")
        root.addWidget(group_hint)

        self.summary = QLabel("Noch keine Datei geladen.")
        self.summary.setStyleSheet("font-weight: 600; padding: 6px 0;")
        root.addWidget(self.summary)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout(); bottom.addStretch()
        self.import_button = QPushButton("Fahrerplanung importieren")
        self.import_button.setEnabled(False); self.import_button.clicked.connect(self._import)
        close = QPushButton("Schließen"); close.clicked.connect(self.reject)
        bottom.addWidget(self.import_button); bottom.addWidget(close); root.addLayout(bottom)

    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Modulon-Ressourcenplaner auswählen", "", "Excel-Dateien (*.xlsx)")
        if not path:
            return
        try:
            self.preview = build_preview(path)
        except Exception as exc:
            QMessageBox.critical(self, "Modulon-Import", str(exc)); return
        self.file_edit.setText(path)
        self._render()

    def _render(self) -> None:
        assert self.preview is not None
        rows = self.preview.rows
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.source_row, row.driver_number, row.personnel_number, row.full_name,
                row.driver_group, row.branch, row.day.strftime("%d.%m.%Y"),
                row.source_status, row.mapped_status,
            ]
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
        unknown = ", ".join(sorted(self.preview.unknown_statuses)) or "keine"
        self.summary.setText(
            f"Monat {self.preview.month:%m/%Y} · {len(rows)} Status-Tage · "
            f"unbekannte Statuswerte: {unknown}"
        )
        self.import_button.setEnabled(bool(self.preview.valid_rows))
        self.table.resizeColumnsToContents()

    def _import(self) -> None:
        if self.preview is None:
            return
        try:
            manual_mappings: dict[str, int] = {}
            unmatched = self.service.unmatched_drivers(self.preview)
            if unmatched:
                drivers = list(self.session.scalars(
                    select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name, Driver.first_name)
                ))
                mapping_dialog = ModulonDriverMappingDialog(unmatched, drivers, self)
                if mapping_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                manual_mappings = mapping_dialog.mappings()
            result = self.service.import_preview(self.preview, manual_mappings=manual_mappings)
        except Exception as exc:
            QMessageBox.critical(self, "Modulon-Import", f"Import fehlgeschlagen:\n{exc}"); return
        text = (
            f"{result.imported} Statustage importiert und zu {result.periods_created} Zeitraum/Zeiträumen zusammengefasst.\n"
            f"{result.replaced} frühere Modulon-Einträge dieses Monats ersetzt.\n"
            f"{result.mappings_created} externe Fahrerzuordnung(en) neu angelegt.\n"
            f"{result.mappings_updated} externe Fahrerzuordnung(en) aktualisiert."
        )
        if result.automatic_matches:
            text += "\n\nAutomatisch zugeordnet und dauerhaft gespeichert:\n" + "\n".join(result.automatic_matches[:20])
            if len(result.automatic_matches) > 20:
                text += f"\n… und {len(result.automatic_matches)-20} weitere"
        if result.unmatched:
            text += "\n\nNicht zugeordnete Fahrer (inkl. externer Kennungen):\n" + "\n".join(result.unmatched[:20])
            if len(result.unmatched) > 20:
                text += f"\n… und {len(result.unmatched)-20} weitere"
        if result.unknown_statuses:
            text += "\n\nUnbekannte Statuswerte wurden als Sperre importiert: " + ", ".join(sorted(result.unknown_statuses))
        QMessageBox.information(self, "Modulon-Import abgeschlossen", text)
        self.accept()
