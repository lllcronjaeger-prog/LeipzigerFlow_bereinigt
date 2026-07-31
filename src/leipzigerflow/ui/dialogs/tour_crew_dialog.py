from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.services.tour_resource_assignment_service import ResourceAssignmentError, TourResourceAssignmentService
from leipzigerflow.services.driver_availability_service import DriverAvailabilityService


class TourCrewDialog(QDialog):
    """Pflegt einen oder mehrere aufeinanderfolgende Fahrerabschnitte."""

    def __init__(self, session, tour, parent=None):
        super().__init__(parent)
        self.session = session
        self.tour = tour
        self.service = TourResourceAssignmentService(session)
        self.drivers = self.service.active_drivers()
        self.schedule = TimePlanningEngine().build_schedule(tour)
        self.availability = DriverAvailabilityService()
        self.setWindowTitle(f"Fahrerzuordnung · {tour.tour_number}")
        self.resize(760, 430)

        root = QVBoxLayout(self)
        base = str(getattr(getattr(tour, "vehicle", None), "home_base", "") or "nicht hinterlegt")
        root.addWidget(QLabel(
            f"Fahrerwechsel sind nur an der Fahrzeugbasis <b>{base}</b> möglich. "
            "Zu jedem Zeitpunkt darf genau ein Fahrer aktiv sein."
        ))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fahrer", "Beginn", "Ende", "Wechselgrund"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        actions = QHBoxLayout()
        add_button = QPushButton("Fahrerabschnitt hinzufügen")
        add_button.clicked.connect(self._add_row)
        actions.addWidget(add_button)
        remove_button = QPushButton("Abschnitt entfernen")
        remove_button.clicked.connect(self._remove_row)
        actions.addWidget(remove_button)
        actions.addStretch()
        root.addLayout(actions)

        scope_form = QFormLayout()
        self.scope = QComboBox()
        self.scope.addItem("Nur diese Tour", "tour")
        self.scope.addItem("Folgetag", "next_day")
        self.scope.addItem("Bis Ende Arbeitsphase (empfohlen)", "phase_end")
        self.scope.addItem("Bis zu einem Datum", "until_date")
        self.scope.addItem("Bis zur nächsten Änderung", "until_changed")
        scope_form.addRow("Übernahme", self.scope)
        self.valid_until = QDateEdit()
        self.valid_until.setCalendarPopup(True)
        self.valid_until.setDisplayFormat("dd.MM.yyyy")
        self.valid_until.setDate(self.valid_until.date().addDays(7))
        self.valid_until.setEnabled(False)
        scope_form.addRow("Gültig bis", self.valid_until)
        self.phase_info = QLabel("Arbeitszeitmodell wird nach Auswahl des Fahrers geprüft.")
        self.phase_info.setWordWrap(True)
        self.phase_info.setObjectName("mutedText")
        scope_form.addRow("Fahrerstatus", self.phase_info)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        root.addLayout(scope_form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        existing = list(getattr(tour, "driver_assignments", []) or [])
        if existing:
            for item in existing:
                self._add_row(item.driver_id, item.starts_at, item.ends_at, item.change_reason)
        else:
            end_at = self.schedule.end_at
            if end_at <= self.schedule.start_at:
                end_at = self.schedule.start_at + timedelta(hours=10)
            self._add_row(getattr(tour, "driver_id", None), self.schedule.start_at, end_at, "")
        self._scope_changed()
        self._update_phase_info()

    def _add_row(self, driver_id=None, starts_at=None, ends_at=None, reason=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        combo = QComboBox()
        combo.addItem("Bitte auswählen", None)
        for driver in self.drivers:
            label = driver.full_name or driver.match_code or f"Fahrer #{driver.id}"
            combo.addItem(label, driver.id)
        if driver_id:
            combo.setCurrentIndex(max(0, combo.findData(driver_id)))
        combo.currentIndexChanged.connect(self._update_phase_info)
        self.table.setCellWidget(row, 0, combo)

        if starts_at is None:
            starts_at = self.schedule.start_at if row == 0 else self._date_time(row - 1, 2)
        if ends_at is None:
            ends_at = self.schedule.end_at
        for col, value in ((1, starts_at), (2, ends_at)):
            edit = QDateTimeEdit(QDateTime(value))
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd.MM.yyyy HH:mm")
            self.table.setCellWidget(row, col, edit)
        self.table.setItem(row, 3, QTableWidgetItem(reason))

    def _date_time(self, row, col):
        return self.table.cellWidget(row, col).dateTime().toPython()


    def _selected_last_driver(self):
        if self.table.rowCount() == 0:
            return None
        combo = self.table.cellWidget(self.table.rowCount() - 1, 0)
        return self.session.get(type(self.drivers[0]), combo.currentData()) if self.drivers and combo.currentData() else None

    def _scope_changed(self):
        self.valid_until.setEnabled(self.scope.currentData() == "until_date")
        self._update_phase_info()

    def _update_phase_info(self):
        driver = self._selected_last_driver()
        if driver is None:
            self.phase_info.setText("Bitte einen Fahrer auswählen.")
            return
        start_day = self.tour.tour_date
        status = self.availability.status(driver, start_day)
        model = str(getattr(driver, "work_model", "MO-FR") or "MO-FR")
        if status.available:
            until = status.available_until.strftime("%d.%m.%Y") if status.available_until else "offen"
            self.phase_info.setText(
                f"Modell: {model} · aktuelle Phase: {status.phase} · verfügbar bis einschließlich {until}. "
                "Modulon-Abwesenheiten haben Vorrang vor dem rechnerischen Modell."
            )
            if status.available_until:
                self.valid_until.setDate(status.available_until)
        else:
            self.phase_info.setText(f"Modell: {model} · nicht verfügbar: {status.reason}")

    def _remove_row(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.rowCount() > 1:
            self.table.removeRow(row)

    def _save(self):
        segments = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if combo.currentData() is None:
                QMessageBox.warning(self, "Fahrerzuordnung", "Bitte in jedem Abschnitt einen Fahrer auswählen.")
                return
            segments.append({
                "driver_id": int(combo.currentData()),
                "starts_at": self._date_time(row, 1),
                "ends_at": self._date_time(row, 2),
                "reason": self.table.item(row, 3).text().strip() if self.table.item(row, 3) else "",
            })
        try:
            scope = self.scope.currentData()
            valid_until = None
            if scope == "next_day":
                valid_until = self.tour.tour_date + timedelta(days=1)
            elif scope == "phase_end":
                driver = self.session.get(type(self.drivers[0]), segments[-1]["driver_id"]) if self.drivers else None
                valid_until = self.availability.continuous_available_until(driver, self.tour.tour_date) if driver else None
                if valid_until is None:
                    raise ResourceAssignmentError("Der Fahrer ist am Tourtag laut Modulon/Arbeitszeitmodell nicht verfügbar.")
            elif scope == "until_date":
                valid_until = self.valid_until.date().toPython()
            self.service.assign_driver_segments(
                self.tour,
                segments,
                propagate_last=scope != "tour",
                valid_until=valid_until,
                until_changed=scope == "until_changed",
            )
        except ResourceAssignmentError as error:
            QMessageBox.warning(self, "Fahrerzuordnung", str(error))
            return
        self.accept()
