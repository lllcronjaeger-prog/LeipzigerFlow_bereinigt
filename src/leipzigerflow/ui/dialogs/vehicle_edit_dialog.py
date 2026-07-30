from datetime import time

from PySide6.QtCore import QByteArray, QDate, QSettings, QTime
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGridLayout, QGroupBox, QLineEdit, QPlainTextEdit,
    QSpinBox, QTabWidget, QTimeEdit, QVBoxLayout, QWidget,
)

from leipzigerflow.models.vehicle import Vehicle, VehicleClass, VehicleOperationType, VehicleOwnership
from leipzigerflow.ui.widgets.resource_absence_editor import ResourceAbsenceEditor


class VehicleEditDialog(QDialog):
    SETTINGS_KEY = "vehicle_edit"
    STATUSES = ["Frei", "Unterwegs", "Auf dem Hof", "Reserviert", "Werkstatt", "Defekt"]

    def __init__(self, vehicle: Vehicle | None = None, trailers=None, drivers=None, locations=None, parent=None):
        super().__init__(parent)
        self.vehicle = vehicle
        self._settings = QSettings("LeipzigerFlow", "VehicleManagement")
        self.trailers = trailers or []
        self.drivers = drivers or []
        self.locations = locations or []
        self.setWindowTitle("Zugmaschine bearbeiten" if vehicle else "Neue Zugmaschine")
        self.setMinimumSize(900, 620)

        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)
        master_page = QWidget(); grid = QGridLayout(master_page)

        self.number = QLineEdit(); self.plate = QLineEdit()
        self.vehicle_class = QComboBox(); self.vehicle_class.addItems(VehicleClass.values())
        self.operation_type = QComboBox(); self.operation_type.addItems(VehicleOperationType.values())
        self.home_base = QComboBox()
        self.home_base.addItem("Bitte Standort auswählen", None)
        for location in self.locations:
            label = getattr(location, "full_display", "") or getattr(location, "name", "")
            self.home_base.addItem(label, getattr(location, "id", None))
        self.daily_return = QCheckBox("Tägliche Rückkehr zur Basis zwingend")
        self.overnight_away = QCheckBox("Tagesruhe außerhalb der Basis zulässig")
        self.operation_type.currentTextChanged.connect(self._sync_operation_rules)
        self.ownership_type = QComboBox(); self.ownership_type.addItems(VehicleOwnership.values())
        self.hu = QDateEdit(); self.hu.setCalendarPopup(True); self.hu.setDisplayFormat("dd.MM.yyyy")
        self.hu.setMinimumDate(QDate(1900, 1, 1)); self.hu.setSpecialValueText("nicht gesetzt"); self.hu.setDate(self.hu.minimumDate())
        self.location = QLineEdit(); self.status = QComboBox(); self.status.addItems(self.STATUSES)
        self.trailer = QComboBox(); self.trailer.addItem("Kein Trailer", None)
        for item in self.trailers: self.trailer.addItem(item.display_name, item.id)
        self.primary_driver = QComboBox(); self.primary_driver.addItem("Kein Stammfahrer", None)
        self.relief_driver = QComboBox(); self.relief_driver.addItem("Kein Wechselfahrer", None)
        for driver in self.drivers:
            self.primary_driver.addItem(driver.full_name, driver.id); self.relief_driver.addItem(driver.full_name, driver.id)
        self.double_shift = QCheckBox("Zweite, zeitlich anschließende Fahrerschicht")
        self.shift_start = QTimeEdit(QTime(6, 0)); self.shift_start.setDisplayFormat("HH:mm")
        self.shift_hours = QSpinBox(); self.shift_hours.setRange(1, 15); self.shift_hours.setValue(10); self.shift_hours.setSuffix(" Stunden")
        self.remarks = QPlainTextEdit(); self.remarks.setMaximumHeight(130)
        self.active = QCheckBox("Aktiv"); self.active.setChecked(True)

        general = QGroupBox("Fahrzeug")
        form = QFormLayout(general)
        for label, widget in (("Fahrzeugnummer", self.number), ("Kennzeichen", self.plate),
            ("Fahrzeugart", self.ownership_type), ("Fahrzeugklasse", self.vehicle_class),
            ("Einsatzart", self.operation_type), ("Heimatbasis", self.home_base),
            ("", self.daily_return), ("", self.overnight_away),
            ("HU", self.hu), ("Standort", self.location), ("Status", self.status),
            ("Gekoppelter Trailer", self.trailer), ("", self.active)):
            form.addRow(label, widget)
        grid.addWidget(general, 0, 0)

        staffing = QGroupBox("Besetzung")
        staffing_form = QFormLayout(staffing)
        staffing_form.addRow("Stammfahrer", self.primary_driver); staffing_form.addRow("Wechselfahrer", self.relief_driver)
        staffing_form.addRow("Schichtbeginn", self.shift_start); staffing_form.addRow("Schichtdauer", self.shift_hours)
        staffing_form.addRow("", self.double_shift); grid.addWidget(staffing, 0, 1)
        notes = QGroupBox("Bemerkung"); notes_layout = QVBoxLayout(notes); notes_layout.addWidget(self.remarks)
        grid.addWidget(notes, 1, 0, 1, 2); grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        tabs.addTab(master_page, "🚛 Stammdaten")

        absence_page = QWidget(); absence_layout = QVBoxLayout(absence_page)
        self.absence_editor = ResourceAbsenceEditor(getattr(vehicle, "absences", ()) if vehicle else (), absence_page)
        absence_layout.addWidget(self.absence_editor)
        tabs.addTab(absence_page, "🛠 Sperrzeiten und Abwesenheiten")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Speichern"); buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

        if vehicle:
            self.number.setText(vehicle.vehicle_number); self.plate.setText(vehicle.license_plate)
            self.vehicle_class.setCurrentText(vehicle.vehicle_class or VehicleClass.STANDARD.value)
            self.operation_type.setCurrentText(getattr(vehicle, "operation_type", VehicleOperationType.LOCAL.value))
            base_id = getattr(vehicle, "home_base_location_id", None)
            idx = self.home_base.findData(base_id) if base_id else -1
            if idx >= 0:
                self.home_base.setCurrentIndex(idx)
            else:
                legacy = (getattr(vehicle, "home_base", "") or "").casefold()
                for row in range(1, self.home_base.count()):
                    if legacy and legacy in self.home_base.itemText(row).casefold():
                        idx = row
                        break
                self.home_base.setCurrentIndex(idx if idx >= 0 else 0)
            self.daily_return.setChecked(bool(getattr(vehicle, "daily_return_required", True)))
            self.overnight_away.setChecked(bool(getattr(vehicle, "overnight_away_allowed", False)))
            self.ownership_type.setCurrentText(getattr(vehicle, "ownership_type", VehicleOwnership.OWN.value))
            if vehicle.hu_date: self.hu.setDate(QDate(vehicle.hu_date.year, vehicle.hu_date.month, vehicle.hu_date.day))
            self.location.setText(vehicle.location); self.status.setCurrentText(vehicle.status)
            self.remarks.setPlainText(vehicle.remarks); self.active.setChecked(vehicle.active)
            self.trailer.setCurrentIndex(max(0, self.trailer.findData(vehicle.trailer_id)))
            profile = getattr(vehicle, "staffing_profile", None)
            if profile:
                self.primary_driver.setCurrentIndex(max(0, self.primary_driver.findData(profile.primary_driver_id)))
                self.relief_driver.setCurrentIndex(max(0, self.relief_driver.findData(profile.relief_driver_id)))
                self.double_shift.setChecked(profile.sequential_double_shift)
                self.shift_start.setTime(QTime(profile.first_shift_start.hour, profile.first_shift_start.minute))
                self.shift_hours.setValue(max(1, round(profile.shift_minutes / 60)))
        self._sync_operation_rules(self.operation_type.currentText())
        self._restore_geometry()


    def _restore_geometry(self) -> None:
        geometry = self._settings.value(f"{self.SETTINGS_KEY}/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            self._ensure_visible_on_screen()
        else:
            self.resize(1100, 760)

    def _ensure_visible_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return
        target = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(self.width(), target.width()), min(self.height(), target.height()))
        self.move(target.center() - self.rect().center())

    def _save_geometry(self) -> None:
        self._settings.setValue(f"{self.SETTINGS_KEY}/geometry", self.saveGeometry())
        self._settings.sync()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self._save_geometry()
        super().closeEvent(event)

    def accept(self) -> None:
        self._save_geometry()
        super().accept()

    def reject(self) -> None:
        self._save_geometry()
        super().reject()

    def _sync_operation_rules(self, value: str) -> None:
        is_local = value == VehicleOperationType.LOCAL.value
        self.daily_return.setChecked(is_local)
        self.overnight_away.setChecked(not is_local)
        self.relief_driver.setEnabled(is_local)
        self.double_shift.setEnabled(is_local)
        if not is_local:
            self.relief_driver.setCurrentIndex(0)
            self.double_shift.setChecked(False)

    def _date(self):
        value = self.hu.date(); return None if value == self.hu.minimumDate() else value.toPython()

    def get_vehicle_data(self):
        return {"vehicle_number": self.number.text().strip(), "license_plate": self.plate.text().strip(),
            "vehicle_class": self.vehicle_class.currentText(), "ownership_type": self.ownership_type.currentText(),
            "operation_type": self.operation_type.currentText(), "home_base": self.home_base.currentText().strip() if self.home_base.currentData() else "",
            "home_base_location_id": self.home_base.currentData(),
            "daily_return_required": self.daily_return.isChecked(), "overnight_away_allowed": self.overnight_away.isChecked(),
            "description": "", "hu_date": self._date(), "location": self.location.text().strip(),
            "status": self.status.currentText(), "trailer_id": self.trailer.currentData(),
            "remarks": self.remarks.toPlainText().strip(), "active": self.active.isChecked(), "is_refrigerated": False}

    def get_staffing_data(self):
        qt = self.shift_start.time()
        is_local = self.operation_type.currentText() == VehicleOperationType.LOCAL.value
        return {"primary_driver_id": self.primary_driver.currentData(), "relief_driver_id": self.relief_driver.currentData() if is_local else None,
            "sequential_double_shift": self.double_shift.isChecked() if is_local else False, "first_shift_start": time(qt.hour(), qt.minute()),
            "shift_minutes": self.shift_hours.value() * 60}

    def get_absence_drafts(self): return self.absence_editor.drafts()
