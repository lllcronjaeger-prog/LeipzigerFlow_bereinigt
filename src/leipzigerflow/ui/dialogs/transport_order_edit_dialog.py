from datetime import time
import json
import re
from decimal import Decimal

from PySide6.QtCore import QDate, QSettings, QTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QPlainTextEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)

from leipzigerflow.services.transport_order_service import (
    TransportOrderService,
)
from leipzigerflow.services.trailer_compatibility import parse_trailer_types


class TransportOrderEditDialog(QDialog):
    def __init__(self, customers, locations, order=None, parent=None):
        super().__init__(parent)
        self._order = order
        self._settings = QSettings("LeipzigerFlow", "TransportOrderTemplates")
        self._syncing_dates = False
        self._loading_order_data = False
        self._locations_by_id = {location.id: location for location in locations}
        self.setWindowTitle("Transportauftrag bearbeiten" if order else "Transportauftrag anlegen")
        self.resize(1120, 760)
        self.setMinimumSize(900, 620)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        form_container = QWidget(scroll_area)
        grid = QGridLayout(form_container)
        grid.setContentsMargins(4, 4, 10, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        # Allgemeine Auftragsdaten
        order_group = QGroupBox("Auftrag")
        order_form = QFormLayout(order_group)
        self.internal_number_label = QLabel(order.order_number if order else "wird automatisch vergeben")
        self.internal_number_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.customer_order_number_edit = QLineEdit()
        self.customer_order_number_edit.setMaxLength(100)
        self.customer_order_number_edit.setPlaceholderText("eindeutige Nummer in der Disposition; bei Umfuhren optional")
        self.dossier_edit = QLineEdit(); self.dossier_edit.setMaxLength(100)
        self.transport_number_edit = QLineEdit(); self.transport_number_edit.setMaxLength(100)
        self.loading_reference_edit = QLineEdit(); self.loading_reference_edit.setMaxLength(150)
        self.unloading_reference_edit = QLineEdit(); self.unloading_reference_edit.setMaxLength(150)
        self.order_type_combo = QComboBox(); self.order_type_combo.addItems(TransportOrderService.ORDER_TYPES)
        self.customer_combo = self._searchable_combo()
        for customer in customers:
            self.customer_combo.addItem(customer.display_name, customer.id)
        self.reference_edit = QLineEdit(); self.reference_edit.setMaxLength(100)
        self.dispatch_priority_combo = QComboBox(); self.dispatch_priority_combo.addItems(TransportOrderService.DISPATCH_PRIORITIES)
        self.status_combo = QComboBox(); self.status_combo.addItems(TransportOrderService.STATUSES)
        self.required_trailer_type_checks = {}
        trailer_type_widget = QWidget()
        trailer_type_layout = QGridLayout(trailer_type_widget)
        trailer_type_layout.setContentsMargins(0, 0, 0, 0)
        for index, trailer_type in enumerate(TransportOrderService.TRAILER_TYPES):
            checkbox = QCheckBox(trailer_type)
            self.required_trailer_type_checks[trailer_type] = checkbox
            trailer_type_layout.addWidget(checkbox, index // 3, index % 3)
        for label, widget in (
            ("Interne Nummer:", self.internal_number_label),
            ("Kundenauftrag:", self.customer_order_number_edit),
            ("Dossier:", self.dossier_edit),
            ("Transportnummer:", self.transport_number_edit),
            ("Ladereferenz:", self.loading_reference_edit),
            ("Entladereferenz:", self.unloading_reference_edit),
            ("Auftragstyp:", self.order_type_combo),
            ("Kunde:", self.customer_combo),
            ("Referenz:", self.reference_edit),
            ("Priorität:", self.dispatch_priority_combo),
            ("Status:", self.status_combo),
            ("Traileraufbauten:", trailer_type_widget),
        ):
            order_form.addRow(label, widget)
        if order is None:
            self.required_trailer_type_checks["Plane"].setChecked(True)
        grid.addWidget(order_group, 0, 0)

        # Transportdaten kompakt rechts oben
        transport_group = QGroupBox("Transportdaten")
        transport_form = QFormLayout(transport_group)
        self.weight_edit = QDoubleSpinBox(); self.weight_edit.setRange(0, 999999999.99); self.weight_edit.setDecimals(2); self.weight_edit.setSuffix(" kg")
        self.loading_meters_edit = QDoubleSpinBox(); self.loading_meters_edit.setRange(0, 99.99); self.loading_meters_edit.setDecimals(2); self.loading_meters_edit.setSuffix(" Ldm")
        self.pallets_edit = QSpinBox(); self.pallets_edit.setRange(0, 99999)
        self.remarks_edit = QPlainTextEdit(); self.remarks_edit.setMaximumHeight(150)
        transport_form.addRow("Gewicht:", self.weight_edit)
        transport_form.addRow("Lademeter:", self.loading_meters_edit)
        transport_form.addRow("Paletten:", self.pallets_edit)
        transport_form.addRow("Bemerkung:", self.remarks_edit)
        template_row = QHBoxLayout()
        load_template_button = QPushButton("Vorlage laden …")
        save_template_button = QPushButton("Als Vorlage speichern …")
        load_template_button.clicked.connect(self._load_template)
        save_template_button.clicked.connect(self._save_template)
        template_row.addWidget(load_template_button); template_row.addWidget(save_template_button)
        transport_form.addRow("Vorlagen:", template_row)
        grid.addWidget(transport_group, 0, 1)

        # Lade- und Entladedaten nebeneinander
        loading_group = QGroupBox("Ladung")
        loading_form = QFormLayout(loading_group)
        self.loading_location_combo = self._searchable_combo()
        for location in locations:
            self.loading_location_combo.addItem(location.full_display, location.id)
        self.loading_date_edit = self._date_edit()
        loading_times = QHBoxLayout(); self.loading_time_from_edit = self._time_edit(); self.loading_time_until_edit = self._time_edit(); loading_times.addWidget(self.loading_time_from_edit); loading_times.addWidget(self.loading_time_until_edit)
        self.loading_time_flexible_check = QCheckBox("Zeitfenster innerhalb der Öffnungszeit verschiebbar"); self.loading_time_flexible_check.setChecked(True)
        loading_open_times = QHBoxLayout(); self.loading_open_from_edit = self._time_edit(); self.loading_open_until_edit = self._time_edit(); loading_open_times.addWidget(self.loading_open_from_edit); loading_open_times.addWidget(self.loading_open_until_edit)
        self.loading_location_hint = QLabel(); self.loading_location_hint.setWordWrap(True); self.loading_location_hint.setStyleSheet("color:#9a6700;")
        loading_form.addRow("Ladestelle:", self.loading_location_combo)
        loading_form.addRow("Ladedatum:", self.loading_date_edit)
        loading_form.addRow("Gebuchtes Zeitfenster:", loading_times)
        loading_form.addRow("", self.loading_time_flexible_check)
        loading_form.addRow("Öffnungszeit:", loading_open_times)
        loading_form.addRow("Standorthinweis:", self.loading_location_hint)
        grid.addWidget(loading_group, 1, 0)

        unloading_group = QGroupBox("Entladung")
        unloading_form = QFormLayout(unloading_group)
        self.unloading_location_combo = self._searchable_combo()
        for location in locations:
            self.unloading_location_combo.addItem(location.full_display, location.id)
        self.unloading_date_edit = self._date_edit()
        unloading_times = QHBoxLayout(); self.unloading_time_from_edit = self._time_edit(); self.unloading_time_until_edit = self._time_edit(); unloading_times.addWidget(self.unloading_time_from_edit); unloading_times.addWidget(self.unloading_time_until_edit)
        self.unloading_time_flexible_check = QCheckBox("Zeitfenster innerhalb der Öffnungszeit verschiebbar"); self.unloading_time_flexible_check.setChecked(True)
        unloading_open_times = QHBoxLayout(); self.unloading_open_from_edit = self._time_edit(); self.unloading_open_until_edit = self._time_edit(); unloading_open_times.addWidget(self.unloading_open_from_edit); unloading_open_times.addWidget(self.unloading_open_until_edit)
        self.unloading_location_hint = QLabel(); self.unloading_location_hint.setWordWrap(True); self.unloading_location_hint.setStyleSheet("color:#9a6700;")
        unloading_form.addRow("Entladestelle:", self.unloading_location_combo)
        unloading_form.addRow("Entladedatum:", self.unloading_date_edit)
        unloading_form.addRow("Gebuchtes Zeitfenster:", unloading_times)
        unloading_form.addRow("", self.unloading_time_flexible_check)
        unloading_form.addRow("Öffnungszeit:", unloading_open_times)
        unloading_form.addRow("Standorthinweis:", self.unloading_location_hint)
        grid.addWidget(unloading_group, 1, 1)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)

        scroll_area.setWidget(form_container)
        outer_layout.addWidget(scroll_area, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        outer_layout.addWidget(buttons)

        self._loading_order_data = True
        if order:
            self._load_order()
        else:
            self._apply_order_type_defaults(force=True)
        self._loading_order_data = False
        self._last_loading_date = self.loading_date_edit.date()
        self.loading_date_edit.dateChanged.connect(self._loading_date_changed)
        self.order_type_combo.currentTextChanged.connect(self._order_type_changed)
        self.loading_location_combo.currentIndexChanged.connect(lambda _index: self._location_changed("loading"))
        self.unloading_location_combo.currentIndexChanged.connect(lambda _index: self._location_changed("unloading"))
        self._location_changed("loading", apply_times=order is None)
        self._location_changed("unloading", apply_times=order is None)
        self.customer_order_number_edit.setFocus()

    @staticmethod
    def _parse_opening_hours(value: str) -> tuple[QTime | None, QTime | None]:
        """Liest den ersten Bereich HH:MM-HH:MM aus den Standortdaten."""
        match = re.search(
            r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})",
            str(value or ""),
        )
        if not match:
            return None, None
        start = QTime(int(match.group(1)), int(match.group(2)))
        end = QTime(int(match.group(3)), int(match.group(4)))
        if not start.isValid() or not end.isValid():
            return None, None
        return start, end

    def _selected_location(self, kind: str):
        combo = (
            self.loading_location_combo
            if kind == "loading"
            else self.unloading_location_combo
        )
        return self._locations_by_id.get(combo.currentData())

    def _location_changed(self, kind: str, *, apply_times: bool = True) -> None:
        if self._loading_order_data:
            return
        location = self._selected_location(kind)
        if kind == "loading":
            open_from_edit = self.loading_open_from_edit
            open_until_edit = self.loading_open_until_edit
            hint_label = self.loading_location_hint
        else:
            open_from_edit = self.unloading_open_from_edit
            open_until_edit = self.unloading_open_until_edit
            hint_label = self.unloading_location_hint

        if location is None:
            hint_label.setText("Kein Standort ausgewaehlt.")
            if apply_times:
                open_from_edit.setTime(QTime(0, 0))
                open_until_edit.setTime(QTime(0, 0))
            return

        opening_hours = str(getattr(location, "opening_hours", "") or "").strip()
        start, end = self._parse_opening_hours(opening_hours)
        if apply_times:
            open_from_edit.setTime(start or QTime(0, 0))
            open_until_edit.setTime(end or QTime(0, 0))

        booking_required = bool(
            getattr(location, "time_window_booking_required", False)
        )
        parts = []
        if opening_hours:
            parts.append(f"Oeffnungszeiten laut Standort: {opening_hours}")
            if start is None or end is None:
                parts.append(
                    "Die Angabe konnte nicht automatisch in Uhrzeiten umgesetzt werden. "
                    "Bitte Format HH:MM-HH:MM verwenden oder im Auftrag manuell eintragen."
                )
        else:
            parts.append("Am Standort sind keine Oeffnungszeiten hinterlegt.")
        if booking_required:
            parts.append("Zeitfensterbuchung ist fuer diesen Standort erforderlich.")
        else:
            parts.append("Keine Pflicht zur Zeitfensterbuchung hinterlegt.")
        hint_label.setText(" · ".join(parts))

    def _missing_required_time_windows(self) -> list[str]:
        missing: list[str] = []
        for kind, title, from_edit, until_edit in (
            ("loading", "Ladestelle", self.loading_time_from_edit, self.loading_time_until_edit),
            ("unloading", "Entladestelle", self.unloading_time_from_edit, self.unloading_time_until_edit),
        ):
            location = self._selected_location(kind)
            if location is None or not bool(
                getattr(location, "time_window_booking_required", False)
            ):
                continue
            if self._python_time(from_edit) is None or self._python_time(until_edit) is None:
                missing.append(f"{title}: {getattr(location, 'full_display', location.name)}")
        return missing

    ORDER_TYPE_DEFAULTS = {
        "Transport": (24000.0, 13.6, 33),
        "Umfuhr": (24000.0, 13.6, 33),
        "Shuttle": (24000.0, 13.6, 33),
        "Leerfahrt": (0.0, 0.0, 0),
        "Sonderfahrt": (24000.0, 13.6, 33),
    }

    def _loading_date_changed(self, new_date: QDate) -> None:
        if self._syncing_dates:
            return
        previous = getattr(self, "_last_loading_date", new_date)
        delta = previous.daysTo(new_date)
        if delta:
            self._syncing_dates = True
            self.unloading_date_edit.setDate(self.unloading_date_edit.date().addDays(delta))
            self._syncing_dates = False
        self._last_loading_date = new_date

    def _order_type_changed(self, _value: str) -> None:
        if self._order is None:
            self._apply_order_type_defaults(force=False)

    def _apply_order_type_defaults(self, *, force: bool) -> None:
        weight, loading_meters, pallets = self.ORDER_TYPE_DEFAULTS.get(
            self.order_type_combo.currentText(),
            self.ORDER_TYPE_DEFAULTS["Transport"],
        )
        if force or (self.weight_edit.value() == 0 and self.loading_meters_edit.value() == 0 and self.pallets_edit.value() == 0):
            self.weight_edit.setValue(weight)
            self.loading_meters_edit.setValue(loading_meters)
            self.pallets_edit.setValue(pallets)

    def _template_data(self) -> dict:
        data = self.get_transport_order_data()
        return {
            "order_type": data["order_type"],
            "dispatch_priority": data["dispatch_priority"],
            "customer_id": data["customer_id"],
            "required_trailer_types": data["required_trailer_types"],
            "loading_location_id": data["loading_location_id"],
            "loading_time_from": self.loading_time_from_edit.time().toString("HH:mm"),
            "loading_time_until": self.loading_time_until_edit.time().toString("HH:mm"),
            "loading_time_flexible": data["loading_time_flexible"],
            "loading_open_from": self.loading_open_from_edit.time().toString("HH:mm"),
            "loading_open_until": self.loading_open_until_edit.time().toString("HH:mm"),
            "unloading_location_id": data["unloading_location_id"],
            "unloading_time_from": self.unloading_time_from_edit.time().toString("HH:mm"),
            "unloading_time_until": self.unloading_time_until_edit.time().toString("HH:mm"),
            "unloading_time_flexible": data["unloading_time_flexible"],
            "unloading_open_from": self.unloading_open_from_edit.time().toString("HH:mm"),
            "unloading_open_until": self.unloading_open_until_edit.time().toString("HH:mm"),
            "weight_kg": float(data["weight_kg"]),
            "loading_meters": float(data["loading_meters"]),
            "pallets": data["pallets"],
            "remarks": data["remarks"],
        }

    def _templates(self) -> dict[str, dict]:
        raw = self._settings.value("templates", "{}", type=str)
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _save_template(self) -> None:
        name, accepted = QInputDialog.getText(self, "Auftragsvorlage", "Name der Vorlage:")
        name = name.strip()
        if not accepted or not name:
            return
        templates = self._templates()
        templates[name] = self._template_data()
        self._settings.setValue("templates", json.dumps(templates, ensure_ascii=False))
        QMessageBox.information(self, "Vorlage gespeichert", f"Die Vorlage „{name}“ wurde gespeichert.")

    def _load_template(self) -> None:
        templates = self._templates()
        if not templates:
            QMessageBox.information(self, "Keine Vorlagen", "Es sind noch keine Auftragsvorlagen gespeichert.")
            return
        names = sorted(templates)
        name, accepted = QInputDialog.getItem(self, "Auftragsvorlage", "Vorlage auswählen:", names, 0, False)
        if not accepted:
            return
        data = templates[name]
        self.order_type_combo.setCurrentText(str(data.get("order_type", "Transport")))
        self.dispatch_priority_combo.setCurrentText(str(data.get("dispatch_priority", "Eigenfuhrpark bevorzugt")))
        self._select(self.customer_combo, data.get("customer_id"))
        self._select(self.loading_location_combo, data.get("loading_location_id"))
        self._select(self.unloading_location_combo, data.get("unloading_location_id"))
        selected_types = set(data.get("required_trailer_types", ["Plane"]))
        for trailer_type, checkbox in self.required_trailer_type_checks.items():
            checkbox.setChecked(trailer_type in selected_types)
        for editor, key in (
            (self.loading_time_from_edit, "loading_time_from"),
            (self.loading_time_until_edit, "loading_time_until"),
            (self.loading_open_from_edit, "loading_open_from"),
            (self.loading_open_until_edit, "loading_open_until"),
            (self.unloading_time_from_edit, "unloading_time_from"),
            (self.unloading_time_until_edit, "unloading_time_until"),
            (self.unloading_open_from_edit, "unloading_open_from"),
            (self.unloading_open_until_edit, "unloading_open_until"),
        ):
            editor.setTime(QTime.fromString(str(data.get(key, "00:00")), "HH:mm"))
        self.loading_time_flexible_check.setChecked(bool(data.get("loading_time_flexible", True)))
        self.unloading_time_flexible_check.setChecked(bool(data.get("unloading_time_flexible", True)))
        self.weight_edit.setValue(float(data.get("weight_kg", 24000)))
        self.loading_meters_edit.setValue(float(data.get("loading_meters", 13.6)))
        self.pallets_edit.setValue(int(data.get("pallets", 33)))
        self.remarks_edit.setPlainText(str(data.get("remarks", "")))

    def accept(self) -> None:
        if self.unloading_date_edit.date() < self.loading_date_edit.date():
            QMessageBox.warning(self, "Eingabe prüfen", "Das Entladedatum darf nicht vor dem Ladedatum liegen.")
            return
        if (
            self.unloading_date_edit.date() == self.loading_date_edit.date()
            and self._python_time(self.loading_time_from_edit)
            and self._python_time(self.unloading_time_until_edit)
            and self._python_time(self.unloading_time_until_edit) < self._python_time(self.loading_time_from_edit)
        ):
            QMessageBox.warning(self, "Eingabe prüfen", "Die Entladung kann am selben Tag nicht vor der Ladung enden.")
            return
        missing_time_windows = self._missing_required_time_windows()
        if missing_time_windows:
            answer = QMessageBox.question(
                self,
                "Zeitfenster fehlt",
                "Bei folgenden Standorten ist eine Zeitfensterbuchung erforderlich, "
                "aber im Auftrag wurde kein vollstaendiges Zeitfenster eingetragen:\n\n"
                + "\n".join(missing_time_windows)
                + "\n\nAuftrag trotzdem speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        warnings = []
        if self.weight_edit.value() > 24000:
            warnings.append(f"Gewicht: {self.weight_edit.value():,.0f} kg")
        if self.loading_meters_edit.value() > 13.6:
            warnings.append(f"Lademeter: {self.loading_meters_edit.value():.2f}")
        if self.pallets_edit.value() > 33:
            warnings.append(f"Paletten: {self.pallets_edit.value()}")
        if warnings:
            answer = QMessageBox.question(
                self,
                "Kapazitätswerte prüfen",
                "Folgende Werte liegen über den Standardwerten:\n\n" + "\n".join(warnings) + "\n\nTrotzdem speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().accept()

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
    def _date_edit() -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd.MM.yyyy")
        editor.setDate(QDate.currentDate())
        return editor

    @staticmethod
    def _time_edit() -> QTimeEdit:
        editor = QTimeEdit()
        editor.setDisplayFormat("HH:mm")
        editor.setTime(QTime(0, 0))
        editor.setSpecialValueText("offen")
        return editor

    @staticmethod
    def _select(
        combo: QComboBox,
        value,
    ) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_time(
        editor: QTimeEdit,
        value,
    ) -> None:
        if value is None:
            editor.setTime(QTime(0, 0))
        else:
            editor.setTime(
                QTime(value.hour, value.minute)
            )

    @staticmethod
    def _python_time(
        editor: QTimeEdit,
    ) -> time | None:
        value = editor.time()
        if value.hour() == 0 and value.minute() == 0:
            return None
        return time(value.hour(), value.minute())

    def _load_order(self) -> None:
        order = self._order

        self.customer_order_number_edit.setText(
            order.customer_order_number
        )
        self.dossier_edit.setText(getattr(order, "dossier", ""))
        self.transport_number_edit.setText(getattr(order, "transport_number", ""))
        self.loading_reference_edit.setText(getattr(order, "loading_reference", ""))
        self.unloading_reference_edit.setText(getattr(order, "unloading_reference", ""))
        self.order_type_combo.setCurrentText(
            order.order_type
        )
        self._select(
            self.customer_combo,
            order.customer_id,
        )
        self.reference_edit.setText(order.reference)
        self.dispatch_priority_combo.setCurrentText(
            getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt")
        )
        self.status_combo.setCurrentText(order.status)
        selected_types = set(parse_trailer_types(
            getattr(order, "required_trailer_type", "Plane")
        ))
        for trailer_type, checkbox in self.required_trailer_type_checks.items():
            checkbox.setChecked(trailer_type in selected_types)

        self._select(
            self.loading_location_combo,
            order.loading_location_id,
        )
        self.loading_date_edit.setDate(
            QDate(
                order.loading_date.year,
                order.loading_date.month,
                order.loading_date.day,
            )
        )
        self._set_time(
            self.loading_time_from_edit,
            order.loading_time_from,
        )
        self._set_time(
            self.loading_time_until_edit,
            order.loading_time_until,
        )
        self.loading_time_flexible_check.setChecked(getattr(order, "loading_time_flexible", True))
        self._set_time(self.loading_open_from_edit, getattr(order, "loading_open_from", None))
        self._set_time(self.loading_open_until_edit, getattr(order, "loading_open_until", None))

        self._select(
            self.unloading_location_combo,
            order.unloading_location_id,
        )
        self.unloading_date_edit.setDate(
            QDate(
                order.unloading_date.year,
                order.unloading_date.month,
                order.unloading_date.day,
            )
        )
        self._set_time(
            self.unloading_time_from_edit,
            order.unloading_time_from,
        )
        self._set_time(
            self.unloading_time_until_edit,
            order.unloading_time_until,
        )
        self.unloading_time_flexible_check.setChecked(getattr(order, "unloading_time_flexible", True))
        self._set_time(self.unloading_open_from_edit, getattr(order, "unloading_open_from", None))
        self._set_time(self.unloading_open_until_edit, getattr(order, "unloading_open_until", None))

        self.weight_edit.setValue(
            float(order.weight_kg)
        )
        self.loading_meters_edit.setValue(
            float(order.loading_meters)
        )
        self.pallets_edit.setValue(order.pallets)
        self.remarks_edit.setPlainText(order.remarks)

    def get_transport_order_data(self):
        return {
            "customer_order_number": (
                self.customer_order_number_edit.text()
            ),
            "dossier": self.dossier_edit.text(),
            "transport_number": self.transport_number_edit.text(),
            "loading_reference": self.loading_reference_edit.text(),
            "unloading_reference": self.unloading_reference_edit.text(),
            "order_type": (
                self.order_type_combo.currentText()
            ),
            "dispatch_priority": self.dispatch_priority_combo.currentText(),
            "customer_id": (
                self.customer_combo.currentData()
            ),
            "reference": self.reference_edit.text(),
            "status": self.status_combo.currentText(),
            "required_trailer_types": [
                trailer_type
                for trailer_type, checkbox
                in self.required_trailer_type_checks.items()
                if checkbox.isChecked()
            ],
            "loading_location_id": (
                self.loading_location_combo.currentData()
            ),
            "loading_date": (
                self.loading_date_edit.date().toPython()
            ),
            "loading_time_from": self._python_time(
                self.loading_time_from_edit
            ),
            "loading_time_until": self._python_time(
                self.loading_time_until_edit
            ),
            "loading_time_flexible": self.loading_time_flexible_check.isChecked(),
            "loading_open_from": self._python_time(self.loading_open_from_edit),
            "loading_open_until": self._python_time(self.loading_open_until_edit),
            "unloading_location_id": (
                self.unloading_location_combo.currentData()
            ),
            "unloading_date": (
                self.unloading_date_edit.date().toPython()
            ),
            "unloading_time_from": self._python_time(
                self.unloading_time_from_edit
            ),
            "unloading_time_until": self._python_time(
                self.unloading_time_until_edit
            ),
            "unloading_time_flexible": self.unloading_time_flexible_check.isChecked(),
            "unloading_open_from": self._python_time(self.unloading_open_from_edit),
            "unloading_open_until": self._python_time(self.unloading_open_until_edit),
            "weight_kg": Decimal(
                str(self.weight_edit.value())
            ),
            "loading_meters": Decimal(
                str(self.loading_meters_edit.value())
            ),
            "pallets": self.pallets_edit.value(),
            "remarks": self.remarks_edit.toPlainText(),
        }
