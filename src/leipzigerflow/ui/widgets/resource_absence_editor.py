from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from leipzigerflow.ui.dialogs.resource_absence_dialog import AbsenceDraft, ResourceAbsenceEditDialog


class ResourceAbsenceEditor(QWidget):
    HEADERS = ("Zustand", "Grund", "Beginn", "Ende", "Bemerkung")

    def __init__(self, absences=(), parent=None):
        super().__init__(parent)
        self._drafts = [AbsenceDraft.from_model(item) for item in absences]
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(170)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        buttons = QHBoxLayout()
        for text, slot in (("➕ Hinzufügen", self.add), ("✏ Bearbeiten", self.edit_selected), ("🗑 Entfernen", self.remove_selected)):
            button = QPushButton(text); button.clicked.connect(slot); buttons.addWidget(button)
        buttons.addStretch(1); root.addLayout(buttons)
        self.refresh()

    def drafts(self) -> list[AbsenceDraft]:
        return list(self._drafts)

    def add(self):
        dialog = ResourceAbsenceEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._drafts.append(dialog.get_draft()); self._sort(); self.refresh()

    def edit_selected(self, *_):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._drafts): return
        dialog = ResourceAbsenceEditDialog(self._drafts[row], self)
        if dialog.exec() == QDialog.Accepted:
            self._drafts[row] = dialog.get_draft(); self._sort(); self.refresh()

    def remove_selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._drafts):
            del self._drafts[row]; self.refresh()

    def _sort(self): self._drafts.sort(key=lambda item: item.starts_at)

    def refresh(self):
        now = datetime.now()
        self.table.setRowCount(len(self._drafts))
        for row, draft in enumerate(self._drafts):
            if not draft.active:
                state = "⚪ Inaktiv"
            elif draft.ends_at <= now:
                state = "⚪ Abgelaufen"
            elif draft.starts_at <= now < draft.ends_at:
                state = "🟠 Aktuell gesperrt"
            else:
                state = "🟡 Geplant"
            values = (state, draft.reason, draft.starts_at.strftime("%d.%m.%Y %H:%M"), draft.ends_at.strftime("%d.%m.%Y %H:%M"), draft.remarks)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
