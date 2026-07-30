from __future__ import annotations

from html import escape
from threading import Event

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from leipzigerflow.ai.provider import AiMessage
from leipzigerflow.ai.service import AiService
from leipzigerflow.database.database import SessionLocal


class _AiRequestWorker(QObject):
    chunk_received = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, question: str, history: list[AiMessage]):
        super().__init__()
        self.question = question
        self.history = list(history)
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        session = SessionLocal()
        try:
            answer = AiService(session).ask_stream(
                self.question,
                self.history,
                self.chunk_received.emit,
                self._cancel_event.is_set,
            )
            if self._cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.completed.emit(answer)
        except Exception as exc:  # Fehler werden kontrolliert an den GUI-Thread übergeben.
            self.failed.emit(str(exc))
        finally:
            session.close()


class AiAssistantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LeipzigerAI – Dispositionsassistent")
        self.resize(900, 680)
        self.messages: list[AiMessage] = []
        self._thread: QThread | None = None
        self._worker: _AiRequestWorker | None = None
        self._current_question = ""
        self._answer_parts: list[str] = []

        root = QVBoxLayout(self)
        title = QLabel("LeipzigerAI – Dispositionsassistent")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        info = QLabel(
            "LeipzigerAI analysiert den aktuellen Datenbestand ausschließlich lesend. "
            "Touranalyse und Optimierungsvorschläge sind in diesem Assistenten zusammengeführt."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.history = QTextBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setHtml(
            "<b>Beispielfragen:</b><br>"
            "• Welche Touren sind in den nächsten Tagen kritisch?<br>"
            "• Welche Aufträge sind noch nicht verplant?<br>"
            "• Wo bestehen freie Kapazitäten?"
        )
        root.addWidget(self.history, 1)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        input_row = QHBoxLayout()
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Frage zur Disposition eingeben …")
        self.prompt_edit.returnPressed.connect(self._send)
        input_row.addWidget(self.prompt_edit, 1)

        self.send_button = QPushButton("Senden")
        self.send_button.clicked.connect(self._send)
        input_row.addWidget(self.send_button)

        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.clicked.connect(self._cancel_request)
        self.cancel_button.setEnabled(False)
        input_row.addWidget(self.cancel_button)
        root.addLayout(input_row)

        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self._request_close)
        root.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _append(self, label: str, text: str) -> None:
        self.history.append(f"<p><b>{escape(label)}</b><br>{escape(text).replace(chr(10), '<br>')}</p>")

    def _start_assistant_answer(self) -> None:
        self.history.append("<p><b>LeipzigerAI</b><br></p>")
        cursor = self.history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history.setTextCursor(cursor)

    @Slot()
    def _send(self) -> None:
        if self._thread is not None:
            return
        question = self.prompt_edit.text().strip()
        if not question:
            return

        self._current_question = question
        self._answer_parts = []
        self.prompt_edit.clear()
        self._append("Sie", question)
        self._start_assistant_answer()
        self._set_busy(True, "LeipzigerAI analysiert die Daten …")

        thread = QThread(self)
        worker = _AiRequestWorker(question, self.messages)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.chunk_received.connect(self._on_chunk)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)

        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(str)
    def _on_chunk(self, chunk: str) -> None:
        self._answer_parts.append(chunk)
        cursor = self.history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.history.setTextCursor(cursor)
        self.history.ensureCursorVisible()
        self.status_label.setText("LeipzigerAI erstellt die Antwort …")

    @Slot(str)
    def _on_completed(self, answer: str) -> None:
        final_answer = answer.strip() or "".join(self._answer_parts).strip()
        if final_answer:
            self.messages.extend(
                [AiMessage("user", self._current_question), AiMessage("assistant", final_answer)]
            )
        self.status_label.setText("Antwort abgeschlossen.")

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._append("Fehler", message)
        QMessageBox.critical(self, "KI-Anfrage fehlgeschlagen", message)

    @Slot()
    def _on_cancelled(self) -> None:
        self._append("System", "Die Anfrage wurde abgebrochen.")

    @Slot()
    def _thread_finished(self) -> None:
        thread = self._thread
        self._worker = None
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        self._set_busy(False)
        self.prompt_edit.setFocus()

    @Slot()
    def _cancel_request(self) -> None:
        if self._worker is None:
            return
        self.status_label.setText("Anfrage wird abgebrochen …")
        self.cancel_button.setEnabled(False)
        self._worker.cancel()

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self.send_button.setEnabled(not busy)
        self.prompt_edit.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setVisible(busy)
        self.status_label.setVisible(busy or bool(status))
        if status:
            self.status_label.setText(status)
        elif not busy:
            self.status_label.setVisible(False)

    def _request_close(self) -> None:
        if self._thread_is_running():
            self._show_running_request_hint()
            return
        super().accept()

    def _thread_is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _show_running_request_hint(self) -> None:
        QMessageBox.information(
            self,
            "KI-Anfrage läuft",
            "Die laufende KI-Anfrage muss zuerst beendet werden. "
            "Klicken Sie auf „Abbrechen“ und warten Sie, bis die Schaltfläche „Senden“ wieder aktiv ist.",
        )

    def accept(self) -> None:
        if self._thread_is_running():
            self._show_running_request_hint()
            return
        super().accept()

    def reject(self) -> None:
        # Auch Escape darf den Dialog nicht zerstören, solange der QThread läuft.
        if self._thread_is_running():
            self._show_running_request_hint()
            return
        super().reject()

    def done(self, result: int) -> None:
        # Zentrale Sicherung für alle Schließwege von QDialog.
        if self._thread_is_running():
            self._show_running_request_hint()
            return
        super().done(result)

    def closeEvent(self, event) -> None:
        if self._thread_is_running():
            self._show_running_request_hint()
            event.ignore()
            return
        super().closeEvent(event)
