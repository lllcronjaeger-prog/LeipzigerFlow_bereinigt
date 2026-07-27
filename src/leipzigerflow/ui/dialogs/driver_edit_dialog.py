from __future__ import annotations

from datetime import date

from PySide6.QtCore import QByteArray, QDate, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.models.driver import Driver


class DriverEditDialog(QDialog):
    """Dialog zum Anlegen und Bearbeiten eines Fahrers.

    Die Fenstergeometrie wird dauerhaft gespeichert. Der Formularinhalt liegt in
    einem Scrollbereich, damit alle Felder auch bei kleineren Fenstern erreichbar
    und sauber ausgerichtet bleiben.
    """

    SETTINGS_ORGANIZATION = "LeipzigerFlow"
    SETTINGS_APPLICATION = "DriverEdit"
    SETTINGS_KEY = "driver_edit_dialog"

    def __init__(self, driver: Driver | None = None, locations=(), parent=None):
        super().__init__(parent)
        self.driver = driver
        self._locations = list(locations or ())
        self._settings = QSettings(
            self.SETTINGS_ORGANIZATION,
            self.SETTINGS_APPLICATION,
        )

        self.setWindowTitle("Fahrer bearbeiten" if driver else "Neuer Fahrer")
        self.setObjectName("driver_edit_dialog")
        self.setMinimumSize(720, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(10)

        scroll = QScrollArea()
        scroll.setObjectName("driver_edit_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll, 1)

        form_page = QWidget()
        form_page.setObjectName("driver_edit_form_page")
        form_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        scroll.setWidget(form_page)

        page_layout = QVBoxLayout(form_page)
        page_layout.setContentsMargins(2, 2, 2, 2)
        page_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        page_layout.addLayout(grid)

        for name in (
            "first_name",
            "last_name",
            "street",
            "house_number",
            "postal_code",
            "city",
            "country",
            "phone",
            "mobile",
            "email",
            "license_number",
            "license_classes",
            "absence_reason",
        ):
            edit = QLineEdit()
            edit.setMinimumWidth(170)
            setattr(self, "edit_" + name, edit)

        self.edit_license_classes.setPlaceholderText("z. B. B, BE, C, CE")
        self.chk_active = QCheckBox("Aktiv")
        self.chk_active.setChecked(True)

        self._dates: dict[str, tuple[QCheckBox, QDateEdit, str]] = {}
        for key, label in (
            ("birth_date", "Geburtsdatum"),
            ("license_valid_until", "Führerschein gültig bis"),
            ("driver_card_valid_until", "Fahrerkarte gültig bis"),
            ("module_95_valid_until", "Module 95 gültig bis"),
            ("adr_valid_until", "ADR gültig bis"),
            ("absence_from", "Abwesend von"),
            ("absence_until", "Abwesend bis"),
        ):
            chk = QCheckBox("Datum erfassen")
            edit = QDateEdit()
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd.MM.yyyy")
            edit.setDate(QDate.currentDate())
            edit.setEnabled(False)
            edit.setMinimumWidth(120)
            chk.toggled.connect(edit.setEnabled)
            self._dates[key] = (chk, edit, label)

        general = QGroupBox("Allgemein")
        general_form = self._new_form_layout(general)
        for label, widget in (
            ("Vorname", self.edit_first_name),
            ("Nachname", self.edit_last_name),
            ("Straße", self.edit_street),
            ("Hausnummer", self.edit_house_number),
            ("PLZ", self.edit_postal_code),
            ("Ort", self.edit_city),
            ("Land", self.edit_country),
        ):
            general_form.addRow(label, widget)
        general_form.addRow("Geburtsdatum", self._date_row("birth_date"))
        grid.addWidget(general, 0, 0)

        contact = QGroupBox("Kontakt")
        contact_form = self._new_form_layout(contact)
        for label, widget in (
            ("Telefon", self.edit_phone),
            ("Mobil", self.edit_mobile),
            ("E-Mail", self.edit_email),
        ):
            contact_form.addRow(label, widget)
        contact_form.addRow("", self.chk_active)
        grid.addWidget(contact, 0, 1)

        qualification = QGroupBox("Qualifikationen und Gültigkeiten")
        qual_grid = QGridLayout(qualification)
        qual_grid.setContentsMargins(12, 12, 12, 12)
        qual_grid.setHorizontalSpacing(18)
        qual_grid.setVerticalSpacing(8)
        qual_grid.setColumnStretch(0, 1)
        qual_grid.setColumnStretch(1, 1)

        left_widget = QWidget()
        left = self._new_form_layout(left_widget)
        left.addRow("Führerscheinnummer", self.edit_license_number)
        left.addRow("Führerscheinklassen", self.edit_license_classes)
        left.addRow("Führerschein gültig bis", self._date_row("license_valid_until"))
        left.addRow("Fahrerkarte gültig bis", self._date_row("driver_card_valid_until"))

        right_widget = QWidget()
        right = self._new_form_layout(right_widget)
        right.addRow("Module 95 gültig bis", self._date_row("module_95_valid_until"))
        right.addRow("ADR gültig bis", self._date_row("adr_valid_until"))

        qual_grid.addWidget(left_widget, 0, 0)
        qual_grid.addWidget(right_widget, 0, 1)
        grid.addWidget(qualification, 1, 0, 1, 2)

        work = QGroupBox("Arbeitsmodell und Disposition")
        work_form = self._new_form_layout(work)
        self.work_model = QComboBox(); self.work_model.addItems(["MO-FR", "2/1", "3/1"])
        self.rotation_start_enabled = QCheckBox("Rotationsbeginn erfassen")
        self.rotation_start = QDateEdit(); self.rotation_start.setCalendarPopup(True); self.rotation_start.setDisplayFormat("dd.MM.yyyy"); self.rotation_start.setDate(QDate.currentDate()); self.rotation_start.setEnabled(False)
        self.rotation_start_enabled.toggled.connect(self.rotation_start.setEnabled)
        rotation_wrap = QWidget(); rotation_row = QGridLayout(rotation_wrap); rotation_row.setContentsMargins(0,0,0,0); rotation_row.addWidget(self.rotation_start_enabled,0,0); rotation_row.addWidget(self.rotation_start,0,1)
        self.home_base = QComboBox()
        self.home_base.addItem("Bitte Standort wählen", None)
        for location in self._locations:
            label = str(getattr(location, "full_display", "") or getattr(location, "name", "") or getattr(location, "city", "") or location)
            self.home_base.addItem(label, int(location.id))
        self.allowed_operation = QComboBox(); self.allowed_operation.addItems(["Beides", "Nahverkehr", "Fernverkehr"])
        self.weekly_target = QSpinBox(); self.weekly_target.setRange(1, 80); self.weekly_target.setValue(48); self.weekly_target.setSuffix(" Stunden")
        self.double_week_limit = QSpinBox(); self.double_week_limit.setRange(1, 120); self.double_week_limit.setValue(96); self.double_week_limit.setSuffix(" Stunden")
        work_form.addRow("Arbeitsmodell", self.work_model); work_form.addRow("Rotationsbeginn", rotation_wrap)
        work_form.addRow("Heimatbasis", self.home_base); work_form.addRow("Zulässiger Einsatz", self.allowed_operation)
        work_form.addRow("Wochenziel", self.weekly_target); work_form.addRow("Grenze Doppelwoche", self.double_week_limit)
        grid.addWidget(work, 2, 0, 1, 2)

        absence = QGroupBox("Aktuelle Abwesenheit")
        absence_grid = QGridLayout(absence)
        absence_grid.setContentsMargins(12, 12, 12, 12)
        absence_grid.setHorizontalSpacing(18)
        absence_grid.setVerticalSpacing(8)
        absence_grid.setColumnStretch(0, 1)
        absence_grid.setColumnStretch(1, 1)

        absence_left_widget = QWidget()
        absence_left = self._new_form_layout(absence_left_widget)
        absence_left.addRow("Abwesend von", self._date_row("absence_from"))
        absence_left.addRow("Abwesend bis", self._date_row("absence_until"))

        absence_right_widget = QWidget()
        absence_right = self._new_form_layout(absence_right_widget)
        absence_right.addRow("Grund", self.edit_absence_reason)

        absence_grid.addWidget(absence_left_widget, 0, 0)
        absence_grid.addWidget(absence_right_widget, 0, 1)
        grid.addWidget(absence, 3, 0, 1, 2)
        page_layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if driver:
            self._load_driver(driver)
        else:
            self.edit_country.setText("Deutschland")

        self._restore_geometry()
        self.edit_first_name.setFocus()

    @staticmethod
    def _new_form_layout(parent: QWidget) -> QFormLayout:
        layout = QFormLayout(parent)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        return layout

    def _date_row(self, key: str) -> QWidget:
        chk, edit, _ = self._dates[key]
        wrap = QWidget()
        row = QGridLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(8)
        row.addWidget(chk, 0, 0)
        row.addWidget(edit, 0, 1)
        row.setColumnStretch(1, 1)
        return wrap

    def _load_driver(self, driver: Driver) -> None:
        for name in (
            "first_name",
            "last_name",
            "street",
            "house_number",
            "postal_code",
            "city",
            "country",
            "phone",
            "mobile",
            "email",
            "license_number",
            "license_classes",
            "absence_reason",
        ):
            getattr(self, "edit_" + name).setText(getattr(driver, name) or "")
        for key, (chk, edit, _) in self._dates.items():
            value = getattr(driver, key, None)
            if value:
                chk.setChecked(True)
                edit.setDate(QDate(value.year, value.month, value.day))
        self.work_model.setCurrentText(getattr(driver, "work_model", "MO-FR") or "MO-FR")
        rotation_start = getattr(driver, "rotation_start", None)
        if rotation_start:
            self.rotation_start_enabled.setChecked(True)
            self.rotation_start.setDate(QDate(rotation_start.year, rotation_start.month, rotation_start.day))
        base_id = getattr(driver, "home_base_location_id", None)
        if base_id is not None:
            index = self.home_base.findData(int(base_id))
            if index >= 0:
                self.home_base.setCurrentIndex(index)
        elif getattr(driver, "home_base", None):
            wanted = str(driver.home_base).casefold()
            for index in range(self.home_base.count()):
                if wanted in self.home_base.itemText(index).casefold():
                    self.home_base.setCurrentIndex(index)
                    break
        self.allowed_operation.setCurrentText(getattr(driver, "allowed_operation", "Beides") or "Beides")
        self.weekly_target.setValue(max(1, round(int(getattr(driver, "weekly_target_minutes", 2880) or 2880) / 60)))
        self.double_week_limit.setValue(max(1, round(int(getattr(driver, "double_week_limit_minutes", 5760) or 5760) / 60)))
        self.chk_active.setChecked(driver.active)

    def _restore_geometry(self) -> None:
        geometry = self._settings.value(f"{self.SETTINGS_KEY}/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            self._ensure_visible_on_screen()
        else:
            self.resize(980, 680)

    def _ensure_visible_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return
        target = QGuiApplication.primaryScreen().availableGeometry()
        width = min(max(self.minimumWidth(), self.width()), target.width())
        height = min(max(self.minimumHeight(), self.height()), target.height())
        self.resize(width, height)
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

    def get_driver_data(self):
        data = {
            name: getattr(self, "edit_" + name).text().strip()
            for name in (
                "first_name",
                "last_name",
                "street",
                "house_number",
                "postal_code",
                "city",
                "country",
                "phone",
                "mobile",
                "email",
                "license_number",
                "license_classes",
                "absence_reason",
            )
        }
        for key, (chk, edit, _) in self._dates.items():
            qdate = edit.date()
            data[key] = (
                date(qdate.year(), qdate.month(), qdate.day())
                if chk.isChecked()
                else None
            )
        data["work_model"] = self.work_model.currentText()
        qrotation = self.rotation_start.date()
        data["rotation_start"] = date(qrotation.year(), qrotation.month(), qrotation.day()) if self.rotation_start_enabled.isChecked() else None
        data["home_base_location_id"] = self.home_base.currentData()
        data["home_base"] = self.home_base.currentText() if self.home_base.currentData() is not None else ""
        data["allowed_operation"] = self.allowed_operation.currentText()
        data["weekly_target_minutes"] = self.weekly_target.value() * 60
        data["double_week_limit_minutes"] = self.double_week_limit.value() * 60
        data["active"] = self.chk_active.isChecked()
        return data
