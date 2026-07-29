from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout,
)

from leipzigerflow.ai.provider import AiMessage
from leipzigerflow.ai.service import AiService
from leipzigerflow.database.database import SessionLocal


class AiAssistantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LeipzigerAI – Dispositionsassistent")
        self.resize(860, 650)
        self.session = SessionLocal()
        self.messages: list[AiMessage] = []
        root = QVBoxLayout(self)
        title = QLabel("LeipzigerAI – Dispositionsassistent")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)
        info = QLabel("Die KI analysiert den aktuellen Datenbestand ausschließlich lesend. Vorschläge werden nicht automatisch übernommen.")
        info.setWordWrap(True); root.addWidget(info)
        self.history = QTextBrowser(); self.history.setOpenExternalLinks(False)
        self.history.setHtml("<b>Beispielfragen:</b><br>• Welche Touren sind in den nächsten Tagen kritisch?<br>• Welche Aufträge sind noch nicht verplant?<br>• Wo bestehen freie Kapazitäten?")
        root.addWidget(self.history, 1)
        row = QHBoxLayout()
        self.prompt_edit = QLineEdit(); self.prompt_edit.setPlaceholderText("Frage zur Disposition eingeben …")
        self.prompt_edit.returnPressed.connect(self._send); row.addWidget(self.prompt_edit, 1)
        self.send_button = QPushButton("Senden"); self.send_button.clicked.connect(self._send); row.addWidget(self.send_button)
        root.addLayout(row)
        close = QPushButton("Schließen"); close.clicked.connect(self.accept); root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _append(self, label: str, text: str) -> None:
        self.history.append(f"<p><b>{label}</b><br>{text.replace(chr(10), '<br>')}</p>")

    def _send(self):
        question = self.prompt_edit.text().strip()
        if not question:
            return
        self.prompt_edit.clear(); self._append("Sie", question)
        self.send_button.setEnabled(False); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            answer = AiService(self.session).ask(question, self.messages)
        except Exception as exc:
            QMessageBox.critical(self, "KI-Anfrage fehlgeschlagen", str(exc))
        else:
            self._append("LeipzigerAI", answer)
            self.messages.extend([AiMessage("user", question), AiMessage("assistant", answer)])
        finally:
            QApplication.restoreOverrideCursor(); self.send_button.setEnabled(True); self.prompt_edit.setFocus()

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
