from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from leipzigerflow.ai.config import (
    AiConfig,
    OLLAMA_DEFAULT_MODEL,
    load_ai_config,
    provider_defaults,
    save_ai_config,
)
from leipzigerflow.ai.service import AiService
from leipzigerflow.database.database import SessionLocal


class AiSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KI-Einstellungen")
        self.resize(680, 500)
        self.config = load_ai_config()

        root = QVBoxLayout(self)
        self.info = QLabel()
        self.info.setWordWrap(True)
        root.addWidget(self.info)

        form = QFormLayout()
        self.enabled = QCheckBox("KI-Anbindung aktivieren")
        self.provider = QComboBox()
        self.provider.addItem("Ollama – lokal und kostenlos (empfohlen)", "ollama")
        self.provider.addItem("OpenAI – Cloud/API-Kosten", "openai")
        self.model = QLineEdit()
        self.base_url = QLineEdit()
        self.api_key_env = QLineEdit()
        self.api_key_label = QLabel("API-Key-Umgebungsvariable:")
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 600)
        self.timeout.setSuffix(" Sekunden")
        self.max_records = QSpinBox()
        self.max_records.setRange(5, 200)

        form.addRow("Status:", self.enabled)
        form.addRow("Anbieter:", self.provider)
        form.addRow("Modell:", self.model)
        form.addRow("Basis-URL:", self.base_url)
        form.addRow(self.api_key_label, self.api_key_env)
        form.addRow("Zeitüberschreitung:", self.timeout)
        form.addRow("Max. Datensätze je Bereich:", self.max_records)
        root.addLayout(form)

        self.ollama_box = QVBoxLayout()
        self.ollama_hint = QLabel(
            "Für die kostenlose lokale Nutzung muss Ollama auf diesem Arbeitsplatz installiert "
            f"und das Modell <b>{OLLAMA_DEFAULT_MODEL}</b> geladen sein. "
            "LeipzigerFlow überträgt dabei keine Unternehmensdaten an einen Cloudanbieter."
        )
        self.ollama_hint.setWordWrap(True)
        self.ollama_box.addWidget(self.ollama_hint)

        command_row = QHBoxLayout()
        self.pull_command = QLineEdit(f"ollama pull {OLLAMA_DEFAULT_MODEL}")
        self.pull_command.setReadOnly(True)
        self.copy_command = QPushButton("Befehl kopieren")
        self.copy_command.clicked.connect(self._copy_pull_command)
        command_row.addWidget(self.pull_command)
        command_row.addWidget(self.copy_command)
        self.ollama_box.addLayout(command_row)
        root.addLayout(self.ollama_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.defaults_button = QPushButton("Empfohlene lokale Werte")
        self.test_button = QPushButton("Verbindung testen")
        buttons.addButton(self.defaults_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self.test_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.defaults_button.clicked.connect(self._apply_provider_defaults)
        self.test_button.clicked.connect(self._test)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.model.textChanged.connect(self._update_pull_command)
        self._load()

    def _load(self) -> None:
        self.enabled.setChecked(self.config.enabled)
        self.provider.setCurrentIndex(max(0, self.provider.findData(self.config.provider)))
        self.model.setText(self.config.model)
        self.base_url.setText(self.config.base_url)
        self.api_key_env.setText(self.config.api_key_env)
        self.timeout.setValue(self.config.timeout_seconds)
        self.max_records.setValue(self.config.max_context_records)
        self._provider_changed()

    def _current(self) -> AiConfig:
        return AiConfig(
            provider=str(self.provider.currentData()),
            model=self.model.text().strip(),
            base_url=self.base_url.text().strip(),
            api_key_env=self.api_key_env.text().strip() or "OPENAI_API_KEY",
            timeout_seconds=self.timeout.value(),
            max_context_records=self.max_records.value(),
            enabled=self.enabled.isChecked(),
        )

    def _provider_changed(self) -> None:
        is_ollama = self.provider.currentData() == "ollama"
        self.api_key_label.setVisible(not is_ollama)
        self.api_key_env.setVisible(not is_ollama)
        self.pull_command.setVisible(is_ollama)
        self.copy_command.setVisible(is_ollama)
        self.ollama_hint.setVisible(is_ollama)
        if is_ollama:
            self.info.setText(
                "<b>Lokale KI:</b> Ollama läuft auf diesem Arbeitsplatz. Es ist kein API-Key "
                "erforderlich und die für eine Anfrage verwendeten LeipzigerFlow-Daten bleiben lokal."
            )
        else:
            self.info.setText(
                "<b>Cloud-KI:</b> API-Schlüssel werden nicht in LeipzigerFlow gespeichert. "
                "Hinterlegen Sie den Schlüssel als Windows-Umgebungsvariable. Bei Cloud-Nutzung "
                "werden die für die Anfrage benötigten Daten an den ausgewählten Anbieter übertragen."
            )

    def _apply_provider_defaults(self) -> None:
        model, base_url = provider_defaults(str(self.provider.currentData()))
        self.model.setText(model)
        self.base_url.setText(base_url)
        if self.provider.currentData() == "ollama":
            self.timeout.setValue(120)
        else:
            self.timeout.setValue(60)

    def _update_pull_command(self) -> None:
        model = self.model.text().strip() or OLLAMA_DEFAULT_MODEL
        self.pull_command.setText(f"ollama pull {model}")

    def _copy_pull_command(self) -> None:
        QGuiApplication.clipboard().setText(self.pull_command.text())
        QMessageBox.information(
            self,
            "Befehl kopiert",
            "Der Ollama-Befehl wurde in die Zwischenablage kopiert.",
        )

    def _test(self) -> None:
        session = SessionLocal()
        try:
            AiService(session, self._current()).test_connection()
        except Exception as exc:
            QMessageBox.critical(self, "Verbindung fehlgeschlagen", str(exc))
        else:
            provider_name = "Ollama" if self.provider.currentData() == "ollama" else "OpenAI"
            QMessageBox.information(
                self,
                "Verbindung erfolgreich",
                f"{provider_name} ist erreichbar und das konfigurierte Modell ist verfügbar.",
            )
        finally:
            session.close()

    def _save(self) -> None:
        config = self._current()
        if not config.model or not config.base_url:
            QMessageBox.warning(self, "Eingabe fehlt", "Bitte Modell und Basis-URL angeben.")
            return
        save_ai_config(config)
        self.accept()
