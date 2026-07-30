from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from leipzigerflow.imports.customer_excel import CustomerImportPreview, build_preview
from leipzigerflow.services.customer_import_service import CustomerImportService


class CustomerImportDialog(QDialog):
    HEADERS = ["Status", "Excel-Zeile", "Name", "MatchCode", "Straße", "PLZ", "Ort", "Frachtzahler", "Hinweis"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.service = CustomerImportService(session)
        self.preview: CustomerImportPreview | None = None
        self.setWindowTitle("Kunden aus Excel importieren")
        self.resize(1280, 720)
        layout = QVBoxLayout(self)
        intro = QLabel("Dispoplan-Kundenstamm auswählen. Name, MatchCode und Anschrift werden übernommen. Der Hauptkunde wird als Frachtzahler verknüpft bzw. automatisch angelegt.")
        intro.setWordWrap(True); layout.addWidget(intro)
        file_row = QHBoxLayout(); self.file_edit = QLineEdit(); self.file_edit.setReadOnly(True)
        choose = QPushButton("Excel-Datei auswählen …"); choose.clicked.connect(self._choose_file)
        file_row.addWidget(self.file_edit, 1); file_row.addWidget(choose); layout.addLayout(file_row)
        self.summary = QLabel("Noch keine Datei geladen."); self.summary.setStyleSheet("font-weight: 600; padding: 6px 0;"); layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.HEADERS)); self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        for i, width in enumerate((85,85,230,150,220,80,150,220,220)): self.table.setColumnWidth(i, width)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table, 1)
        bottom = QHBoxLayout(); bottom.addWidget(QLabel("Doppelklick erlaubt Korrekturen vor dem Import.")); bottom.addStretch()
        self.import_button = QPushButton("Gültige Kunden importieren"); self.import_button.setEnabled(False); self.import_button.clicked.connect(self._import)
        close = QPushButton("Schließen"); close.clicked.connect(self.reject); bottom.addWidget(self.import_button); bottom.addWidget(close); layout.addLayout(bottom)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Dispoplan-Kundenstamm auswählen", "", "Excel-Dateien (*.xls *.xlsx)")
        if not path: return
        try: self.preview = self.service.mark_existing(build_preview(path))
        except Exception as exc:
            QMessageBox.critical(self, "Kundenimport", str(exc)); return
        self.file_edit.setText(path); self._show_preview()

    def _show_preview(self):
        assert self.preview is not None
        self.table.setRowCount(len(self.preview.rows))
        for r, row in enumerate(self.preview.rows):
            payer = " | ".join(v for v in (row.freight_payer_match_code, row.freight_payer_name) if v)
            values = (row.status, str(row.source_row), row.name, row.match_code, f"{row.street} {row.house_number}".strip(), row.postal_code, row.city, payer, "; ".join(row.errors))
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c in (0,1): item.setFlags(item.flags() & ~Qt.ItemIsEditable); item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r,c,item)
        new = sum(r.status == "Neu" for r in self.preview.rows); updates = sum(r.status == "Update" for r in self.preview.rows)
        self.summary.setText(f"{len(self.preview.rows)} Kunden gefunden · {new} neu · {updates} Aktualisierungen · {len(self.preview.error_rows)} Fehler")
        self.import_button.setEnabled(bool(self.preview.valid_rows))

    def _sync_changes(self):
        import re
        assert self.preview is not None
        for i, row in enumerate(self.preview.rows):
            row.name = self.table.item(i,2).text().strip(); row.match_code = self.table.item(i,3).text().strip()
            street = self.table.item(i,4).text().strip(); m = re.match(r"^(.*?)(?:\s+)(\d+[\w\-/]*)$", street)
            row.street, row.house_number = (m.group(1).strip(), m.group(2).strip()) if m else (street, "")
            row.postal_code = self.table.item(i,5).text().strip(); row.city = self.table.item(i,6).text().strip()
            payer = self.table.item(i,7).text().strip()
            if "|" in payer: row.freight_payer_match_code, row.freight_payer_name = [p.strip() for p in payer.split("|",1)]
            else: row.freight_payer_name = payer
            row.errors.clear()
            if not row.name: row.errors.append("Name fehlt")
            if not row.match_code: row.errors.append("MatchCode fehlt")
            if not row.city: row.errors.append("Ort fehlt")

    def _import(self):
        if self.preview is None: return
        self._sync_changes(); self.service.mark_existing(self.preview)
        if self.preview.error_rows and QMessageBox.question(self, "Kundenimport", f"{len(self.preview.error_rows)} fehlerhafte Zeile(n) werden übersprungen. Fortfahren?") != QMessageBox.Yes:
            self._show_preview(); return
        try: result = self.service.import_rows(self.preview.rows)
        except Exception as exc:
            QMessageBox.critical(self, "Kundenimport", f"Import fehlgeschlagen:\n{exc}"); return
        QMessageBox.information(self, "Kundenimport abgeschlossen", f"{result.created} Kunden neu angelegt.\n{result.updated} Kunden aktualisiert.\n{result.freight_payers_created} Frachtzahler neu angelegt.\n{result.skipped} Zeilen übersprungen.")
        self.accept()
