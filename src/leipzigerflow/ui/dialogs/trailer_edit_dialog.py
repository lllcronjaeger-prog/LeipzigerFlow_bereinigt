from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGridLayout, QGroupBox, QLineEdit, QPlainTextEdit,
    QTabWidget, QVBoxLayout, QWidget,
)

from leipzigerflow.models.trailer import Trailer, TrailerType
from leipzigerflow.ui.widgets.resource_absence_editor import ResourceAbsenceEditor


class TrailerEditDialog(QDialog):
    STATUSES = ["Frei", "Unterwegs", "Beladen", "Beim Kunden", "Auf dem Hof", "Reserviert", "Werkstatt", "Defekt"]

    def __init__(self, trailer: Trailer | None = None, parent=None):
        super().__init__(parent); self.trailer = trailer
        self.setWindowTitle("Trailer bearbeiten" if trailer else "Neuer Trailer")
        self.resize(820, 560); self.setMinimumSize(720, 500)
        root = QVBoxLayout(self); tabs = QTabWidget(); root.addWidget(tabs, 1)
        master = QWidget(); grid = QGridLayout(master)
        self.number = QLineEdit(); self.plate = QLineEdit(); self.type = QComboBox(); self.type.addItems(TrailerType.values())
        self.hu = self._date_edit(); self.sp = self._date_edit(); self.location = QLineEdit()
        self.status = QComboBox(); self.status.addItems(self.STATUSES)
        self.remarks = QPlainTextEdit(); self.remarks.setMaximumHeight(130)
        self.active = QCheckBox("Aktiv"); self.active.setChecked(True)
        general = QGroupBox("Allgemein"); general_form = QFormLayout(general)
        general_form.addRow("Trailernummer", self.number); general_form.addRow("Kennzeichen", self.plate)
        general_form.addRow("Trailertyp", self.type); general_form.addRow("Standort", self.location); grid.addWidget(general, 0, 0)
        status_group = QGroupBox("Status und Termine"); status_form = QFormLayout(status_group)
        status_form.addRow("Status", self.status); status_form.addRow("HU", self.hu); status_form.addRow("SP", self.sp); status_form.addRow("", self.active)
        grid.addWidget(status_group, 0, 1)
        notes = QGroupBox("Bemerkung"); notes_layout = QVBoxLayout(notes); notes_layout.addWidget(self.remarks)
        grid.addWidget(notes, 1, 0, 1, 2); grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        tabs.addTab(master, "🚚 Stammdaten")
        absence_page = QWidget(); absence_layout = QVBoxLayout(absence_page)
        self.absence_editor = ResourceAbsenceEditor(getattr(trailer, "absences", ()) if trailer else (), absence_page)
        absence_layout.addWidget(self.absence_editor); tabs.addTab(absence_page, "🛠 Sperrzeiten und Abwesenheiten")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Speichern"); buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        if trailer:
            self.number.setText(trailer.trailer_number); self.plate.setText(trailer.license_plate); self.type.setCurrentText(trailer.trailer_type)
            if trailer.hu_date: self.hu.setDate(QDate(trailer.hu_date.year, trailer.hu_date.month, trailer.hu_date.day))
            if trailer.sp_date: self.sp.setDate(QDate(trailer.sp_date.year, trailer.sp_date.month, trailer.sp_date.day))
            self.location.setText(trailer.location); self.status.setCurrentText(trailer.status)
            self.remarks.setPlainText(trailer.remarks); self.active.setChecked(trailer.active)

    @staticmethod
    def _date_edit() -> QDateEdit:
        widget = QDateEdit(); widget.setCalendarPopup(True); widget.setDisplayFormat("dd.MM.yyyy")
        widget.setSpecialValueText("nicht gesetzt"); widget.setMinimumDate(QDate(1900, 1, 1)); widget.setDate(widget.minimumDate()); return widget
    @staticmethod
    def _date(widget):
        value = widget.date(); return None if value == widget.minimumDate() else value.toPython()
    def get_data(self):
        return {"trailer_number": self.number.text().strip(), "license_plate": self.plate.text().strip(),
            "trailer_type": self.type.currentText(), "hu_date": self._date(self.hu), "sp_date": self._date(self.sp),
            "location": self.location.text().strip(), "status": self.status.currentText(),
            "remarks": self.remarks.toPlainText().strip(), "active": self.active.isChecked()}
    def get_absence_drafts(self): return self.absence_editor.drafts()
