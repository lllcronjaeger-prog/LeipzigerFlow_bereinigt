from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)
from sqlalchemy import select

from leipzigerflow.models.disposition_import_rule import DispositionImportRule


FIELDS = ["Unternehmer", "Fahrzeug", "Fahrer", "Frachtzahler", "Beladestelle", "Entladestelle"]
OPERATORS = ["ist gleich", "enthält", "beginnt mit", "endet mit", "Platzhalter", "Regex"]
ACTIONS = [
    "Auftrag ignorieren",
    "Disposition offen",
    "Kein Subunternehmer",
    "Interner Hinweis",
    "Fest an Subunternehmer vergeben",
    "Unternehmer ersetzen",
]


class RuleEditDialog(QDialog):
    def __init__(self, rule: DispositionImportRule | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importregel bearbeiten")
        self.resize(560, 390)
        form = QFormLayout(self)
        self.name = QLineEdit(rule.name if rule else "")
        self.field = QComboBox(); self.field.addItems(FIELDS)
        self.operator = QComboBox(); self.operator.addItems(OPERATORS)
        self.value = QLineEdit(rule.comparison_value if rule else "")
        self.action = QComboBox(); self.action.addItems(ACTIONS)
        self.owner = QLineEdit(rule.responsibility_hint if rule else "")
        self.replacement = QLineEdit(rule.replacement_contractor if rule else "")
        self.priority = QSpinBox(); self.priority.setRange(1, 9999); self.priority.setValue(rule.priority if rule else 100)
        self.active = QCheckBox("Regel aktiv"); self.active.setChecked(rule.active if rule else True)
        if rule:
            for combo, value in ((self.field, rule.field_name), (self.operator, rule.operator), (self.action, rule.action)):
                index = combo.findText(value)
                if index >= 0: combo.setCurrentIndex(index)
        form.addRow("Name", self.name); form.addRow("Feld", self.field); form.addRow("Bedingung", self.operator)
        form.addRow("Vergleichswert", self.value); form.addRow("Aktion", self.action)
        form.addRow("Zuständigkeit/Hinweis", self.owner); form.addRow("Unternehmer ersetzen durch", self.replacement)
        form.addRow("Priorität", self.priority); form.addRow("", self.active)
        note = QLabel("Bei „Disposition offen“ wird der Auftrag importiert, bleibt für die Auto-Disposition verfügbar und der Unternehmertext kann als Zuständigkeitshinweis erhalten bleiben.")
        note.setWordWrap(True); form.addRow(note)
        buttons = QHBoxLayout(); buttons.addStretch()
        save = QPushButton("Speichern"); cancel = QPushButton("Abbrechen")
        save.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        buttons.addWidget(save); buttons.addWidget(cancel); form.addRow(buttons)

    def values(self) -> dict:
        return dict(name=self.name.text().strip(), field_name=self.field.currentText(), operator=self.operator.currentText(),
                    comparison_value=self.value.text().strip(), action=self.action.currentText(),
                    responsibility_hint=self.owner.text().strip(), replacement_contractor=self.replacement.text().strip(),
                    priority=self.priority.value(), active=self.active.isChecked())


class DispositionImportRuleDialog(QDialog):
    HEADERS = ["Prio", "Aktiv", "Name", "Feld", "Bedingung", "Wert", "Aktion", "Zuständigkeit"]

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Regeln für den Dispositionsimport")
        self.resize(1120, 650)
        layout = QVBoxLayout(self)
        text = QLabel("Die erste passende aktive Regel wird angewendet. Regeln mit kleinerer Prioritätszahl werden zuerst geprüft.")
        text.setWordWrap(True); layout.addWidget(text)
        self.table = QTableWidget(0, len(self.HEADERS)); self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        for label, handler in (("Neu", self._new), ("Bearbeiten", self._edit), ("Löschen", self._delete)):
            button = QPushButton(label); button.clicked.connect(handler); buttons.addWidget(button)
        buttons.addStretch(); close = QPushButton("Schließen"); close.clicked.connect(self.accept); buttons.addWidget(close)
        layout.addLayout(buttons); self._load()

    def _load(self):
        self.rules = list(self.session.scalars(select(DispositionImportRule).order_by(DispositionImportRule.priority, DispositionImportRule.id)))
        self.table.setRowCount(len(self.rules))
        for r, rule in enumerate(self.rules):
            values = [rule.priority, "Ja" if rule.active else "Nein", rule.name, rule.field_name, rule.operator, rule.comparison_value, rule.action, rule.responsibility_hint]
            for c, value in enumerate(values): self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def _selected(self):
        row = self.table.currentRow()
        return self.rules[row] if 0 <= row < len(self.rules) else None

    def _new(self):
        dialog = RuleEditDialog(parent=self)
        if dialog.exec():
            values = dialog.values()
            if not values["name"] or not values["comparison_value"]:
                QMessageBox.warning(self, "Importregel", "Name und Vergleichswert müssen ausgefüllt sein."); return
            self.session.add(DispositionImportRule(**values)); self.session.commit(); self._load()

    def _edit(self):
        rule = self._selected()
        if rule is None: return
        dialog = RuleEditDialog(rule, self)
        if dialog.exec():
            for key, value in dialog.values().items(): setattr(rule, key, value)
            self.session.commit(); self._load()

    def _delete(self):
        rule = self._selected()
        if rule is None: return
        if QMessageBox.question(self, "Importregel", f"Regel „{rule.name}“ wirklich löschen?") != QMessageBox.StandardButton.Yes: return
        self.session.delete(rule); self.session.commit(); self._load()
