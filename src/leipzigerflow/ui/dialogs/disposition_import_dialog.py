from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from leipzigerflow.imports.disposition_excel import build_preview
from leipzigerflow.services.disposition_import_service import DispositionImportService


class DispositionImportDialog(QDialog):
    HEADERS = ["Status", "Excel-Zeile", "Transportnummer", "Ladetermin", "Beladestelle", "Entladestelle", "Fahrzeug", "Fahrer", "Hinweis"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = DispositionImportService(session)
        self.preview = None
        self.setWindowTitle("Disposition synchronisieren")
        self.resize(1450, 820)
        layout = QVBoxLayout(self)
        intro = QLabel("Die Dispoplan-Disposition kann mehrmals täglich importiert werden. Standorte, Transportaufträge und bereits verplante Touren werden neu angelegt oder anhand ihrer eindeutigen Nummern aktualisiert. XLS und XLSX werden unterstützt.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.file_edit = QLineEdit(); self.file_edit.setReadOnly(True)
        choose = QPushButton("Dispositionsdatei auswählen …"); choose.clicked.connect(self._choose_file)
        row.addWidget(self.file_edit, 1); row.addWidget(choose); layout.addLayout(row)
        self.summary = QLabel("Noch keine Datei geladen."); self.summary.setStyleSheet("font-weight: 600; padding: 6px 0;")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.HEADERS)); self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        widths = [80, 90, 170, 100, 250, 250, 130, 170]
        for index, width in enumerate(widths): self.table.setColumnWidth(index, width)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table, 1)
        bottom = QHBoxLayout(); bottom.addWidget(QLabel("Wiederholte Importe aktualisieren vorhandene Datensätze und erzeugen keine Dubletten.")); bottom.addStretch()
        self.import_button = QPushButton("Disposition synchronisieren"); self.import_button.setEnabled(False); self.import_button.clicked.connect(self._import)
        close = QPushButton("Schließen"); close.clicked.connect(self.reject)
        bottom.addWidget(self.import_button); bottom.addWidget(close); layout.addLayout(bottom)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Dispoplan-Disposition auswählen", "", "Excel-Dateien (*.xls *.xlsx)")
        if not path: return
        try: self.preview = self.service.mark_existing(build_preview(path))
        except Exception as exc:
            QMessageBox.critical(self, "Dispositionsimport", str(exc)); return
        self.file_edit.setText(path); self._show_preview()

    def _show_preview(self):
        self.table.setRowCount(len(self.preview.rows))
        for index, row in enumerate(self.preview.rows):
            values = [row.status, str(row.source_row), row.transport_number, row.loading_date.strftime("%d.%m.%Y") if row.loading_date else "", row.loading_address.name, row.unloading_address.name, row.vehicle, row.driver, "; ".join(row.errors)]
            for column, value in enumerate(values): self.table.setItem(index, column, QTableWidgetItem(value))
        new_count = sum(row.status == "Neu" for row in self.preview.rows); updates = sum(row.status == "Update" for row in self.preview.rows); planned = sum(row.has_planning for row in self.preview.valid_rows)
        self.summary.setText(f"{len(self.preview.rows)} Aufträge · {new_count} neu · {updates} Aktualisierungen · {planned} bereits verplant · {len(self.preview.error_rows)} Fehler")
        self.import_button.setEnabled(bool(self.preview.valid_rows))

    def _import(self):
        if self.preview is None: return
        if self.preview.error_rows:
            answer = QMessageBox.question(self, "Dispositionsimport", f"{len(self.preview.error_rows)} fehlerhafte Zeile(n) werden übersprungen. Fortfahren?")
            if answer != QMessageBox.StandardButton.Yes: return
        try: result = self.service.import_rows(self.preview.rows)
        except Exception as exc:
            QMessageBox.critical(self, "Dispositionsimport", f"Synchronisation fehlgeschlagen:\n{exc}"); return
        QMessageBox.information(self, "Disposition synchronisiert", f"{result.locations_created} Standorte neu · {result.locations_updated} aktualisiert\n{result.orders_created} Aufträge neu · {result.orders_updated} aktualisiert\n{result.tours_created} Touren neu · {result.tours_updated} aktualisiert\n{result.tour_assignments} Aufträge einer Tour zugeordnet\n{result.skipped} Zeilen übersprungen")
        self.accept()
