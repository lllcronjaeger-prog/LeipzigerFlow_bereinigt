from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from leipzigerflow.services.tour_service import (
    TourService,
)


class TourEditDialog(QDialog):
    def __init__(
        self,
        drivers,
        vehicles,
        tour=None,
        parent=None,
    ):
        super().__init__(parent)
        self._tour = tour

        self.setWindowTitle(
            "Tour bearbeiten"
            if tour
            else "Tour anlegen"
        )
        self.resize(560, 430)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.tour_number_label = QLabel(
            tour.tour_number
            if tour
            else "wird automatisch vergeben"
        )
        self.tour_number_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.tour_date_edit = QDateEdit()
        self.tour_date_edit.setCalendarPopup(True)
        self.tour_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.tour_date_edit.setDate(QDate.currentDate())

        self.planned_start_time_edit = QTimeEdit()
        self.planned_start_time_edit.setDisplayFormat("HH:mm")
        self.planned_start_time_edit.setTime(QTime(6, 0))

        self.driver_combo = self._searchable_combo()
        self.driver_combo.addItem(
            "Nicht zugewiesen",
            None,
        )
        for driver in drivers:
            self.driver_combo.addItem(
                self._driver_name(driver),
                driver.id,
            )

        self.vehicle_combo = self._searchable_combo()
        self.vehicle_combo.addItem(
            "Nicht zugewiesen",
            None,
        )
        for vehicle in vehicles:
            self.vehicle_combo.addItem(
                self._vehicle_name(vehicle),
                vehicle.id,
            )

        self.status_combo = QComboBox()
        self.status_combo.addItems(
            TourService.STATUSES
        )

        self.remarks_edit = QPlainTextEdit()
        self.remarks_edit.setMaximumHeight(120)

        form.addRow(
            "Tournummer:",
            self.tour_number_label,
        )
        form.addRow(
            "Tourdatum:",
            self.tour_date_edit,
        )
        form.addRow("Geplanter Start:", self.planned_start_time_edit)
        form.addRow(
            "Fahrer:",
            self.driver_combo,
        )
        form.addRow(
            "Fahrzeug:",
            self.vehicle_combo,
        )
        form.addRow(
            "Status:",
            self.status_combo,
        )
        form.addRow(
            "Bemerkung:",
            self.remarks_edit,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if tour:
            self._load_tour()

    @staticmethod
    def _searchable_combo() -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )
        combo.completer().setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        combo.completer().setFilterMode(
            Qt.MatchFlag.MatchContains
        )
        return combo

    @staticmethod
    def _driver_name(driver) -> str:
        display_name = getattr(
            driver,
            "display_name",
            "",
        )
        if display_name:
            return str(display_name)

        return (
            f"{getattr(driver, 'first_name', '')} "
            f"{getattr(driver, 'last_name', '')}"
        ).strip()

    @staticmethod
    def _vehicle_name(vehicle) -> str:
        plate = getattr(
            vehicle,
            "license_plate",
            "",
        )
        description = getattr(
            vehicle,
            "description",
            "",
        )
        if plate and description:
            return f"{plate} – {description}"
        return str(plate or description)

    @staticmethod
    def _select(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_tour(self) -> None:
        tour = self._tour

        self.tour_date_edit.setDate(
            QDate(
                tour.tour_date.year,
                tour.tour_date.month,
                tour.tour_date.day,
            )
        )
        if tour.planned_start_time:
            self.planned_start_time_edit.setTime(QTime(tour.planned_start_time.hour, tour.planned_start_time.minute))
        self._select(
            self.driver_combo,
            tour.driver_id,
        )
        self._select(
            self.vehicle_combo,
            tour.vehicle_id,
        )
        self.status_combo.setCurrentText(tour.status)
        self.remarks_edit.setPlainText(tour.remarks)

    def get_tour_data(self):
        return {
            "tour_date": (
                self.tour_date_edit.date().toPython()
            ),
            "planned_start_time": self.planned_start_time_edit.time().toPython(),
            "driver_id": self.driver_combo.currentData(),
            "vehicle_id": (
                self.vehicle_combo.currentData()
            ),
            "status": self.status_combo.currentText(),
            "remarks": self.remarks_edit.toPlainText(),
        }
