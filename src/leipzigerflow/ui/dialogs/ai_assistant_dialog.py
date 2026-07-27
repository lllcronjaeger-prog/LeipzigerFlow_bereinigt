from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout,
)


class AiAssistantDialog(QDialog):
    """Vorbereitete Oberfläche für den späteren Dispositionsassistenten."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KI-Dispositionsassistent")
        self.resize(760, 560)

        root = QVBoxLayout(self)
        title = QLabel("KI-Dispositionsassistent")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        info = QLabel(
            "Die Oberfläche ist vorbereitet. Eine aktive ChatGPT- oder Suchmaschinen-"
            "Verbindung wird erst nach Einrichtung eines API-Zugangs freigeschaltet."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.history = QTextBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setHtml(
            "<b>Beispielfragen:</b><br>"
            "• Welche Touren sind morgen kritisch?<br>"
            "• Welches Fahrzeug ist für Tour 123 verfügbar?<br>"
            "• Warum hat eine Tour eine rote Bewertung?<br>"
            "• Welche Fahrzeuge wurden diesen Monat wenig eingesetzt?"
        )
        root.addWidget(self.history, 1)

        input_row = QHBoxLayout()
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Frage zur Disposition eingeben …")
        self.prompt_edit.returnPressed.connect(self._not_configured)
        input_row.addWidget(self.prompt_edit, 1)
        send_button = QPushButton("Senden")
        send_button.clicked.connect(self._not_configured)
        input_row.addWidget(send_button)
        root.addLayout(input_row)

        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        root.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _not_configured(self):
        QMessageBox.information(
            self,
            "Noch nicht verbunden",
            "Der KI-Assistent ist vorbereitet, aber noch nicht mit einem API-Zugang verbunden.",
        )
