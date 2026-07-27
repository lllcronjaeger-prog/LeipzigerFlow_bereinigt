from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class TransportOrderSeriesDialog(QDialog):
    def __init__(self, order, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Auftragsserie erzeugen")
        self.resize(430, 220)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Aus dem Auftrag "
            f"{order.order_number} wird eine Serie erzeugt.\n"
            "Jeder Auftrag erhält eine neue interne Nummer "
            "und den Status „Neu“."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 500)
        self.count_spin.setValue(3)

        self.interval_combo = QComboBox()
        self.interval_combo.addItem(
            "Gleiche Zeiten",
            0,
        )
        self.interval_combo.addItem(
            "15 Minuten",
            15,
        )
        self.interval_combo.addItem(
            "30 Minuten",
            30,
        )
        self.interval_combo.addItem(
            "60 Minuten",
            60,
        )
        self.interval_combo.addItem(
            "90 Minuten",
            90,
        )
        self.interval_combo.addItem(
            "120 Minuten",
            120,
        )

        form.addRow(
            "Anzahl neuer Aufträge:",
            self.count_spin,
        )
        form.addRow(
            "Zeitabstand:",
            self.interval_combo,
        )
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def count(self) -> int:
        return self.count_spin.value()

    def interval_minutes(self) -> int:
        return int(self.interval_combo.currentData())
