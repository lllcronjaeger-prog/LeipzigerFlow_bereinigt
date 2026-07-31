from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from leipzigerflow.models.driver import Driver


class DriverMergeDialog(QDialog):
    def __init__(self, source: Driver, targets: list[Driver], parent=None):
        super().__init__(parent)
        self.source = source
        self.setWindowTitle("Fahrer zusammenführen")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        info = QLabel(
            "Alle Touren, Fahrerabschnitte, Modulon-Abwesenheiten und Fahrzeugbesetzungen "
            "des Quellfahrers werden auf den Zielfahrer übertragen. Der Quellfahrer wird "
            "anschließend archiviert."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        source_label = QLabel(f"{source.full_name}  ·  ID {source.id}")
        source_label.setStyleSheet("font-weight: 600;")
        form.addRow("Quellfahrer:", source_label)

        self.target_combo = QComboBox()
        for driver in targets:
            details = []
            if driver.personnel_number:
                details.append(f"Personal-Nr. {driver.personnel_number}")
            if driver.modulon_driver_number:
                details.append(f"Modulon {driver.modulon_driver_number}")
            suffix = f" · {' · '.join(details)}" if details else ""
            self.target_combo.addItem(f"{driver.full_name} · ID {driver.id}{suffix}", driver.id)
        form.addRow("Zielfahrer:", self.target_combo)
        root.addLayout(form)

        warning = QLabel(
            "Hinweis: Das Zusammenführen kann nicht automatisch rückgängig gemacht werden. "
            "Historische Daten bleiben erhalten."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #9a5a00;")
        root.addWidget(warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Zusammenführen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def target_driver_id(self) -> int | None:
        value = self.target_combo.currentData()
        return int(value) if value is not None else None
