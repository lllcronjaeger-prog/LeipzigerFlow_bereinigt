from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
    QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout,
)

from leipzigerflow.models.resource_absence import AbsenceReason


@dataclass(slots=True)
class AbsenceDraft:
    starts_at: datetime
    ends_at: datetime
    reason: str
    remarks: str = ""
    active: bool = True
    source_id: int | None = None

    @classmethod
    def from_model(cls, item):
        return cls(item.starts_at, item.ends_at, item.reason, item.remarks, item.active, item.id)


class ResourceAbsenceEditDialog(QDialog):
    def __init__(self, draft: AbsenceDraft | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sperrzeit bearbeiten" if draft else "Neue Sperrzeit")
        self.setMinimumWidth(520)

        now = datetime.now().replace(second=0, microsecond=0)
        start = draft.starts_at if draft else now
        end = draft.ends_at if draft else now + timedelta(hours=8)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.reason = QComboBox(); self.reason.addItems(AbsenceReason.values())
        self.starts_at = QDateTimeEdit(QDateTime(start)); self.starts_at.setCalendarPopup(True); self.starts_at.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.ends_at = QDateTimeEdit(QDateTime(end)); self.ends_at.setCalendarPopup(True); self.ends_at.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.remarks = QPlainTextEdit(); self.remarks.setMaximumHeight(100)
        self.active = QCheckBox("Sperrzeit aktiv"); self.active.setChecked(True)
        form.addRow("Grund", self.reason)
        form.addRow("Beginn", self.starts_at)
        form.addRow("Ende", self.ends_at)
        form.addRow("Bemerkung", self.remarks)
        form.addRow("", self.active)
        root.addLayout(form)
        hint = QLabel("Die Ressource wird nur während des angegebenen Zeitraums gesperrt und danach automatisch wieder freigegeben.")
        hint.setWordWrap(True); hint.setObjectName("mutedText"); root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Übernehmen")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._source_id = draft.source_id if draft else None
        if draft:
            self.reason.setCurrentText(draft.reason)
            self.remarks.setPlainText(draft.remarks)
            self.active.setChecked(draft.active)

    def _accept_checked(self):
        if self.ends_at.dateTime() <= self.starts_at.dateTime():
            self.ends_at.setFocus()
            return
        self.accept()

    def get_draft(self) -> AbsenceDraft:
        return AbsenceDraft(
            starts_at=self.starts_at.dateTime().toPython(),
            ends_at=self.ends_at.dateTime().toPython(),
            reason=self.reason.currentText(),
            remarks=self.remarks.toPlainText().strip(),
            active=self.active.isChecked(),
            source_id=self._source_id,
        )
