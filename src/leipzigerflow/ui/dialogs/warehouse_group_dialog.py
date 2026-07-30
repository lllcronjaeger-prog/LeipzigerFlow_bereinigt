from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from leipzigerflow.models.warehouse import WarehouseGroup


class WarehouseGroupEditDialog(QDialog):
    def __init__(self, group: WarehouseGroup | None = None, parent=None):
        super().__init__(parent)
        self.group = group
        self.setWindowTitle("Lagergruppe bearbeiten" if group else "Neue Lagergruppe")
        form = QFormLayout()
        self.name = QLineEdit()
        self.aliases = QLineEdit()
        self.aliases.setPlaceholderText("z. B. LIDL;Lidl Vertriebs-GmbH")
        self.hours = {}
        for key, label in (
            ("monday_hours", "Montag"), ("tuesday_hours", "Dienstag"),
            ("wednesday_hours", "Mittwoch"), ("thursday_hours", "Donnerstag"),
            ("friday_hours", "Freitag"), ("saturday_hours", "Samstag"),
            ("sunday_hours", "Sonntag"),
        ):
            edit = QLineEdit()
            edit.setPlaceholderText("z. B. 06:00-13:00")
            self.hours[key] = edit
            form.addRow(label, edit)
        self.loading = QSpinBox(); self.loading.setRange(0, 600); self.loading.setSuffix(" min")
        self.unloading = QSpinBox(); self.unloading.setRange(0, 600); self.unloading.setSuffix(" min")
        self.waiting = QSpinBox(); self.waiting.setRange(0, 600); self.waiting.setSuffix(" min")
        self.active = QCheckBox("Aktiv"); self.active.setChecked(True)
        form.insertRow(0, "Name", self.name)
        form.insertRow(1, "Suchbegriffe", self.aliases)
        form.addRow("Standard-Ladedauer", self.loading)
        form.addRow("Standard-Entladedauer", self.unloading)
        form.addRow("Standard-Wartezeit", self.waiting)
        form.addRow("", self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
        if group:
            self.name.setText(group.name); self.aliases.setText(group.aliases)
            for key, edit in self.hours.items(): edit.setText(getattr(group, key))
            self.loading.setValue(group.standard_loading_minutes)
            self.unloading.setValue(group.standard_unloading_minutes)
            self.waiting.setValue(group.standard_waiting_minutes)
            self.active.setChecked(group.active)

    def data(self) -> dict:
        result = {
            "name": self.name.text().strip(), "aliases": self.aliases.text().strip(),
            "standard_loading_minutes": self.loading.value(),
            "standard_unloading_minutes": self.unloading.value(),
            "standard_waiting_minutes": self.waiting.value(), "active": self.active.isChecked(),
        }
        result.update({key: edit.text().strip() for key, edit in self.hours.items()})
        return result


class WarehouseGroupDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Lagergruppen")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>🏷️ Lagergruppen</h2><p>Öffnungszeiten werden im Hintergrund auf alle zugeordneten Läger übertragen.</p>"))
        self.list = QListWidget(); self.list.itemDoubleClicked.connect(self.edit)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        new = QPushButton("➕ Neu"); edit = QPushButton("✏️ Bearbeiten"); close = QPushButton("Schließen")
        new.clicked.connect(self.new); edit.clicked.connect(self.edit); close.clicked.connect(self.accept)
        buttons.addWidget(new); buttons.addWidget(edit); buttons.addStretch(); buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.groups = list(self.session.scalars(select(WarehouseGroup).order_by(WarehouseGroup.name)))
        self.list.clear()
        for group in self.groups:
            hours = group.monday_hours or "keine Standardzeit"
            self.list.addItem(f"{'🟢' if group.active else '⚪'} {group.name} · Mo {hours}")

    def selected(self):
        row = self.list.currentRow()
        return self.groups[row] if 0 <= row < len(self.groups) else None

    def new(self):
        dialog = WarehouseGroupEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        data = dialog.data()
        if not data["name"]:
            QMessageBox.warning(self, "Lagergruppe", "Bitte einen Namen eingeben."); return
        self.session.add(WarehouseGroup(**data)); self.session.commit(); self.refresh()

    def edit(self):
        group = self.selected()
        if group is None: return
        dialog = WarehouseGroupEditDialog(group, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        for key, value in dialog.data().items(): setattr(group, key, value)
        self.session.commit(); self.refresh()
