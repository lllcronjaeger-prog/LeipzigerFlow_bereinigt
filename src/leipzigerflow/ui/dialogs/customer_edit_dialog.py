from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from leipzigerflow.models.customer import Customer


class CustomerEditDialog(QDialog):
    def __init__(
        self,
        customer: Customer | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.customer = customer

        self.setWindowTitle(
            "Kunde bearbeiten"
            if customer
            else "Neuer Kunde"
        )

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.edit_name = QLineEdit()

        self.edit_short_name = QLineEdit()
        self.edit_short_name.setPlaceholderText(
            "z. B. BMW, AMZ, DAC"
        )

        self.edit_street = QLineEdit()
        self.edit_house_number = QLineEdit()

        self.edit_postal_code = QLineEdit()
        self.edit_city = QLineEdit()
        self.edit_country = QLineEdit()

        self.edit_phone = QLineEdit()
        self.edit_email = QLineEdit()
        self.edit_website = QLineEdit()

        self.edit_vat_number = QLineEdit()
        self.edit_vat_number.setPlaceholderText(
            "z. B. DE123456789"
        )

        self.priority = QSpinBox()
        self.priority.setRange(1, 10)
        self.priority.setValue(5)
        self.priority.setToolTip("10 = höchste Priorität in der automatischen Disposition")
        self.chk_own_fleet = QCheckBox("Eigenfuhrpark bevorzugen")
        self.chk_subcontracting = QCheckBox("Verkauf an Subunternehmer zulässig")
        self.chk_subcontracting.setChecked(True)

        self.chk_active = QCheckBox("Aktiv")
        self.chk_active.setChecked(True)

        form.addRow("Name", self.edit_name)
        form.addRow("Kurzname", self.edit_short_name)
        form.addRow("Straße", self.edit_street)
        form.addRow("Hausnummer", self.edit_house_number)
        form.addRow("PLZ", self.edit_postal_code)
        form.addRow("Ort", self.edit_city)
        form.addRow("Land", self.edit_country)
        form.addRow("Telefon", self.edit_phone)
        form.addRow("E-Mail", self.edit_email)
        form.addRow("Webseite", self.edit_website)
        form.addRow("USt-IdNr.", self.edit_vat_number)
        form.addRow("Dispositionspriorität", self.priority)
        form.addRow("", self.chk_own_fleet)
        form.addRow("", self.chk_subcontracting)
        form.addRow("", self.chk_active)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        if customer is not None:
            self.edit_name.setText(customer.name)
            self.edit_short_name.setText(
                customer.short_name
            )

            self.edit_street.setText(customer.street)
            self.edit_house_number.setText(
                customer.house_number
            )
            self.edit_postal_code.setText(
                customer.postal_code
            )
            self.edit_city.setText(customer.city)
            self.edit_country.setText(customer.country)

            self.edit_phone.setText(customer.phone)
            self.edit_email.setText(customer.email)
            self.edit_website.setText(customer.website)

            self.edit_vat_number.setText(
                customer.vat_number
            )

            self.priority.setValue(max(1, min(10, int(getattr(customer, "disposition_priority", 5) or 5))))
            self.chk_own_fleet.setChecked(bool(getattr(customer, "own_fleet_preferred", False)))
            self.chk_subcontracting.setChecked(bool(getattr(customer, "subcontracting_allowed", True)))
            self.chk_active.setChecked(customer.active)

        else:
            self.edit_country.setText("Deutschland")

        self.edit_name.setFocus()

    def get_customer_data(self) -> dict:
        return {
            "name": self.edit_name.text().strip(),
            "short_name": (
                self.edit_short_name.text().strip()
            ),
            "street": self.edit_street.text().strip(),
            "house_number": (
                self.edit_house_number.text().strip()
            ),
            "postal_code": (
                self.edit_postal_code.text().strip()
            ),
            "city": self.edit_city.text().strip(),
            "country": self.edit_country.text().strip(),
            "phone": self.edit_phone.text().strip(),
            "email": self.edit_email.text().strip(),
            "website": self.edit_website.text().strip(),
            "vat_number": (
                self.edit_vat_number.text().strip()
            ),
            "disposition_priority": self.priority.value(),
            "own_fleet_preferred": self.chk_own_fleet.isChecked(),
            "subcontracting_allowed": self.chk_subcontracting.isChecked(),
            "active": self.chk_active.isChecked(),
        }