from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType


class LocationEditDialog(QDialog):
    def __init__(
        self,
        location: Location | None = None,
        parent=None,
        customers=None,
    ):
        super().__init__(parent)

        self.location = location

        self.setWindowTitle(
            "Standort bearbeiten"
            if location
            else "Neuer Standort"
        )

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.cmb_type = QComboBox()
        self.cmb_customer = QComboBox()
        self.cmb_customer.addItem("— kein Kunde —", None)
        for customer in customers or []:
            self.cmb_customer.addItem(customer.display_name, customer.id)

        for location_type in LocationType:
            self.cmb_type.addItem(
                location_type.display_name,
                location_type,
            )

        self.edit_name = QLineEdit()

        self.edit_short_name = QLineEdit()
        self.edit_short_name.setPlaceholderText(
            "z. B. BMW, AMZ, DAC"
        )

        self.edit_aliases = QLineEdit()
        self.edit_aliases.setPlaceholderText(
            "z. B. Werk;Nordtor;BMW Leipzig"
        )

        self.edit_street = QLineEdit()
        self.edit_house_number = QLineEdit()

        self.edit_postal_code = QLineEdit()
        self.edit_city = QLineEdit()
        self.edit_country = QLineEdit()

        self.edit_contact_person = QLineEdit()
        self.edit_phone = QLineEdit()
        self.edit_email = QLineEdit()

        self.edit_opening_hours = QLineEdit()
        self.edit_opening_hours.setPlaceholderText("z. B. 06:00-18:00")
        self.chk_time_window_required = QCheckBox(
            "Für diesen Standort muss ein Zeitfenster gebucht werden"
        )
        self.chk_group_defaults = QCheckBox("Standardwerte der Lagergruppe verwenden")
        self.btn_reset_group_defaults = QPushButton("↺ Auf Standard der Lagergruppe zurücksetzen")
        self.btn_reset_group_defaults.clicked.connect(self._reset_to_group_defaults)

        self.loading_duration_spin = QSpinBox()
        self.loading_duration_spin.setRange(0, 600)
        self.loading_duration_spin.setSuffix(" min")
        self.loading_duration_spin.setValue(60)
        self.unloading_duration_spin = QSpinBox()
        self.unloading_duration_spin.setRange(0, 600)
        self.unloading_duration_spin.setSuffix(" min")
        self.unloading_duration_spin.setValue(60)

        self.chk_active = QCheckBox("Aktiv")
        self.chk_active.setChecked(True)

        form.addRow("Typ", self.cmb_type)
        form.addRow("Zugehöriger Kunde", self.cmb_customer)
        form.addRow("Name", self.edit_name)
        form.addRow("Kurzname", self.edit_short_name)
        form.addRow("Suchbegriffe", self.edit_aliases)
        form.addRow("Straße", self.edit_street)
        form.addRow("Hausnummer", self.edit_house_number)
        form.addRow("PLZ", self.edit_postal_code)
        form.addRow("Ort", self.edit_city)
        form.addRow("Land", self.edit_country)
        form.addRow("Ansprechpartner", self.edit_contact_person)
        form.addRow("Telefon", self.edit_phone)
        form.addRow("E-Mail", self.edit_email)
        form.addRow("Öffnungszeiten", self.edit_opening_hours)
        form.addRow("", self.chk_group_defaults)
        form.addRow("", self.btn_reset_group_defaults)
        form.addRow("", self.chk_time_window_required)
        form.addRow("Ladedauer", self.loading_duration_spin)
        form.addRow("Entladedauer", self.unloading_duration_spin)
        form.addRow("", self.chk_active)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        if location is not None:

            index = self.cmb_type.findData(
                location.location_type
            )

            if index >= 0:
                self.cmb_type.setCurrentIndex(index)

            customer_index = self.cmb_customer.findData(location.customer_id)
            if customer_index >= 0:
                self.cmb_customer.setCurrentIndex(customer_index)

            self.edit_name.setText(location.name)
            self.edit_short_name.setText(location.short_name)
            self.edit_aliases.setText(location.aliases)

            self.edit_street.setText(location.street)
            self.edit_house_number.setText(location.house_number)
            self.edit_postal_code.setText(location.postal_code)
            self.edit_city.setText(location.city)
            self.edit_country.setText(location.country)
            self.edit_contact_person.setText(location.contact_person)
            self.edit_phone.setText(location.phone)
            self.edit_email.setText(location.email)
            self.edit_opening_hours.setText(location.opening_hours)
            self.chk_group_defaults.setChecked(bool(getattr(location, "use_warehouse_group_defaults", False)))
            has_group = getattr(location, "warehouse_group", None) is not None
            self.chk_group_defaults.setEnabled(has_group)
            self.btn_reset_group_defaults.setEnabled(has_group)
            self.chk_time_window_required.setChecked(
                bool(getattr(location, "time_window_booking_required", False))
                or str(getattr(location, "time_window", "") or "").strip().lower()
                in {"ja", "yes", "required", "pflicht", "erforderlich"}
            )
            self.loading_duration_spin.setValue(location.loading_duration_minutes)
            self.unloading_duration_spin.setValue(location.unloading_duration_minutes)

            self.chk_active.setChecked(location.active)

        else:
            self.edit_country.setText("Deutschland")
            self.chk_group_defaults.setEnabled(False)
            self.btn_reset_group_defaults.setEnabled(False)

        self.chk_group_defaults.toggled.connect(self._group_defaults_toggled)
        self._group_defaults_toggled(self.chk_group_defaults.isChecked())

    def _reset_to_group_defaults(self):
        group = getattr(self.location, "warehouse_group", None) if self.location is not None else None
        if group is None:
            return
        self.edit_opening_hours.setText(group.monday_hours or "")
        self.loading_duration_spin.setValue(max(0, int(group.standard_loading_minutes or 0)))
        self.unloading_duration_spin.setValue(max(0, int(group.standard_unloading_minutes or 0)))
        self.chk_group_defaults.setChecked(True)

    def _group_defaults_toggled(self, enabled: bool):
        has_group = self.location is not None and getattr(self.location, "warehouse_group", None) is not None
        inherited = bool(enabled and has_group)
        self.edit_opening_hours.setEnabled(not inherited)
        self.loading_duration_spin.setEnabled(not inherited)
        self.unloading_duration_spin.setEnabled(not inherited)

    def get_location_data(self):

        return {
            "location_type": self.cmb_type.currentData(),
            "customer_id": self.cmb_customer.currentData(),
            "name": self.edit_name.text().strip(),
            "short_name": self.edit_short_name.text().strip(),
            "aliases": self.edit_aliases.text().strip(),
            "street": self.edit_street.text().strip(),
            "house_number": self.edit_house_number.text().strip(),
            "postal_code": self.edit_postal_code.text().strip(),
            "city": self.edit_city.text().strip(),
            "country": self.edit_country.text().strip(),
            "contact_person": self.edit_contact_person.text().strip(),
            "phone": self.edit_phone.text().strip(),
            "email": self.edit_email.text().strip(),
            "opening_hours": self.edit_opening_hours.text().strip(),
            "use_warehouse_group_defaults": self.chk_group_defaults.isChecked(),
            # Das alte Freitextfeld wird bewusst geleert. Die fachliche Aussage
            # wird jetzt eindeutig ueber das Kontrollkaestchen gespeichert.
            "time_window": "",
            "time_window_booking_required": self.chk_time_window_required.isChecked(),
            "loading_duration_minutes": self.loading_duration_spin.value(),
            "unloading_duration_minutes": self.unloading_duration_spin.value(),
            "active": self.chk_active.isChecked(),
        }