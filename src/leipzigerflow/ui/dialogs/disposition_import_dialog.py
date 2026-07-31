from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from leipzigerflow.imports.disposition_excel import build_preview
from leipzigerflow.services.disposition_import_service import DispositionImportService


class DispositionImportDialog(QDialog):
    HEADERS = ["Status", "Excel-Zeile", "Kundenauftrag", "Dossier", "Ladetermin", "Beladestelle", "Entladestelle", "Fahrzeug", "Fahrer", "Hinweis"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = DispositionImportService(session)
        self.preview = None
        self.setWindowTitle("Disposition synchronisieren")
        self.resize(1450, 820)
        layout = QVBoxLayout(self)
        intro = QLabel("Die Dispoplan-Disposition kann mehrmals täglich importiert werden. Standorte, Transportaufträge und bereits verplante Touren werden neu angelegt oder vorrangig anhand ihrer eindeutigen Kundenauftragsnummer aktualisiert. XLS und XLSX werden unterstützt.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.file_edit = QLineEdit(); self.file_edit.setReadOnly(True)
        choose = QPushButton("Dispositionsdatei auswählen …"); choose.clicked.connect(self._choose_file)
        rules = QPushButton("Importregeln …"); rules.clicked.connect(self._open_rules)
        row.addWidget(self.file_edit, 1); row.addWidget(choose); row.addWidget(rules); layout.addLayout(row)
        self.summary = QLabel("Noch keine Datei geladen."); self.summary.setStyleSheet("font-weight: 600; padding: 6px 0;")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.HEADERS)); self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        widths = [80, 90, 180, 120, 100, 240, 240, 130, 170]
        for index, width in enumerate(widths): self.table.setColumnWidth(index, width)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table, 1)
        bottom = QHBoxLayout(); bottom.addWidget(QLabel("Wiederholte Importe aktualisieren vorhandene Datensätze und erzeugen keine Dubletten.")); bottom.addStretch()
        self.import_button = QPushButton("Disposition synchronisieren"); self.import_button.setEnabled(False); self.import_button.clicked.connect(self._import)
        close = QPushButton("Schließen"); close.clicked.connect(self.reject)
        bottom.addWidget(self.import_button); bottom.addWidget(close); layout.addLayout(bottom)

    def _open_rules(self):
        from leipzigerflow.ui.dialogs.disposition_import_rule_dialog import DispositionImportRuleDialog
        if DispositionImportRuleDialog(self.session, parent=self).exec() and self.file_edit.text():
            try:
                self.preview = self.service.mark_existing(build_preview(self.file_edit.text()))
                self._show_preview()
            except Exception as exc:
                QMessageBox.critical(self, "Dispositionsimport", str(exc))

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
            hint = "; ".join(row.errors)
            if row.rule_name:
                rule_text = f"Regel: {row.rule_name} → {row.rule_action}"
                if row.responsibility_hint:
                    rule_text += f" · Zuständig: {row.responsibility_hint}"
                hint = "; ".join(filter(None, (hint, rule_text)))
            values = [row.status, str(row.source_row), row.customer_order_number, row.dossier, row.loading_date.strftime("%d.%m.%Y") if row.loading_date else "", row.loading_address.name, row.unloading_address.name, row.vehicle, row.driver, hint]
            for column, value in enumerate(values): self.table.setItem(index, column, QTableWidgetItem(value))
        new_count = sum(row.status == "Neu" for row in self.preview.rows); updates = sum(row.status == "Update" for row in self.preview.rows); planned = sum(row.has_planning for row in self.preview.valid_rows); ignored = sum(row.status == "Ignoriert" for row in self.preview.rows); open_disp = sum(row.rule_action == "Disposition offen" for row in self.preview.valid_rows)
        self.summary.setText(f"{len(self.preview.rows)} Datensätze · {new_count} neu · {updates} Aktualisierungen · {planned} bereits verplant · {open_disp} Disposition offen · {ignored} ignoriert · {len(self.preview.error_rows)} Fehler")
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
