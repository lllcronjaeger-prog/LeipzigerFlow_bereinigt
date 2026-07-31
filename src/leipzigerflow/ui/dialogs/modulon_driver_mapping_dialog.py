from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ModulonDriverMappingDialog(QDialog):
    """Resolve ambiguous Modulon driver records before the monthly import.

    The selected association is persisted as an external mapping by the import
    service, so it is normally required only once per Modulon driver number.
    """

    HEADERS = ("Modulon-Fahrer", "Modulon-ID", "Personal-Nr.", "LeipzigerFlow-Fahrer")

    def __init__(self, unmatched, drivers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modulon-Fahrer zuordnen")
        self.resize(920, 420)
        self._unmatched = list(unmatched)
        self._drivers = list(drivers)
        self._combos: list[QComboBox] = []

        root = QVBoxLayout(self)
        info = QLabel(
            "Für diese Modulon-Datensätze wurde kein eindeutiger automatischer Treffer gefunden. "
            "Bitte einmalig den vorhandenen Fahrer auswählen. Die Zuordnung wird dauerhaft über die "
            "Modulon-ID gespeichert. Eine leere Auswahl lässt den Fahrer unzugeordnet."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        table = QTableWidget(len(self._unmatched), len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        for row_index, item in enumerate(self._unmatched):
            values = (item.full_name, item.driver_number or "–", item.personnel_number or "–")
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_index, column, cell)

            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.addItem("Nicht zuordnen", None)
            suggested_ids = {candidate.driver_id for candidate in item.candidates}
            ordered = sorted(
                self._drivers,
                key=lambda driver: (
                    0 if int(driver.id) in suggested_ids else 1,
                    str(driver.last_name or "").casefold(),
                    str(driver.first_name or "").casefold(),
                ),
            )
            for driver in ordered:
                label = driver.full_name
                details = []
                if getattr(driver, "personnel_number", None):
                    details.append(f"Pers.-Nr. {driver.personnel_number}")
                if getattr(driver, "city", None):
                    details.append(driver.city)
                if details:
                    label += " · " + " · ".join(details)
                combo.addItem(label, int(driver.id))

            if item.candidates:
                best = item.candidates[0]
                index = combo.findData(best.driver_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
                    combo.setToolTip(f"Vorschlag: {best.reason} ({best.score:.0%})")
            self._combos.append(combo)
            table.setCellWidget(row_index, 3, combo)

        root.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Zuordnungen übernehmen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def mappings(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item, combo in zip(self._unmatched, self._combos):
            driver_id = combo.currentData()
            if driver_id is not None and item.external_id:
                result[item.external_id] = int(driver_id)
        return result
