from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)
from sqlalchemy import create_engine, text

from leipzigerflow.config.database_config import DatabaseConfig, load_database_config, save_database_config


class DatabaseSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datenbank und zentraler Speicher")
        self.resize(620, 420)
        self.config = load_database_config()

        root = QVBoxLayout(self)
        info = QLabel(
            "SQLite ist für Einzelplatzbetrieb gedacht. Für mehrere gleichzeitig arbeitende "
            "Disponenten verwenden Sie PostgreSQL auf einem Server. Änderungen werden nach "
            "einem Neustart von LeipzigerFlow aktiv."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Betriebsart:"))
        self.mode = QComboBox()
        self.mode.addItem("Einzelplatz (SQLite)", "sqlite")
        self.mode.addItem("Mehrbenutzer (PostgreSQL)", "postgresql")
        self.mode.currentIndexChanged.connect(self._change_page)
        mode_row.addWidget(self.mode, 1)
        root.addLayout(mode_row)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        self.stack.addWidget(self._sqlite_page())
        self.stack.addWidget(self._postgres_page())

        storage_form = QFormLayout()
        storage_row = QHBoxLayout()
        self.document_root = QLineEdit(self.config.document_root)
        storage_row.addWidget(self.document_root, 1)
        browse_documents = QPushButton("Ordner wählen …")
        browse_documents.clicked.connect(self._browse_documents)
        storage_row.addWidget(browse_documents)
        storage_form.addRow("Dokumente/Exporte:", storage_row)
        self.refresh_seconds = QSpinBox()
        self.refresh_seconds.setRange(1, 60)
        self.refresh_seconds.setValue(self.config.refresh_seconds)
        self.refresh_seconds.setSuffix(" Sekunden")
        storage_form.addRow("Plantafel-Aktualisierung:", self.refresh_seconds)
        root.addLayout(storage_form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        test_button = buttons.addButton("Verbindung testen", QDialogButtonBox.ButtonRole.ActionRole)
        test_button.clicked.connect(self._test_connection)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_values()

    def _sqlite_page(self):
        page = QWidget()
        form = QFormLayout(page)
        row = QHBoxLayout()
        self.sqlite_file = QLineEdit()
        row.addWidget(self.sqlite_file, 1)
        browse = QPushButton("Datei wählen …")
        browse.clicked.connect(self._browse_sqlite)
        row.addWidget(browse)
        form.addRow("Datenbankdatei:", row)
        warning = QLabel("Keine SQLite-Datei gleichzeitig von mehreren PCs in einem Netzwerkordner öffnen.")
        warning.setWordWrap(True)
        form.addRow("Hinweis:", warning)
        return page

    def _postgres_page(self):
        page = QWidget()
        form = QFormLayout(page)
        self.host = QLineEdit()
        self.port = QSpinBox(); self.port.setRange(1, 65535)
        self.database = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Server:", self.host)
        form.addRow("Port:", self.port)
        form.addRow("Datenbank:", self.database)
        form.addRow("Benutzer:", self.username)
        form.addRow("Passwort:", self.password)
        return page

    def _load_values(self):
        index = self.mode.findData(self.config.mode)
        self.mode.setCurrentIndex(max(0, index))
        self.sqlite_file.setText(self.config.sqlite_file)
        self.host.setText(self.config.host)
        self.port.setValue(self.config.port)
        self.database.setText(self.config.database)
        self.username.setText(self.config.username)
        self.password.setText(self.config.password)
        self._change_page()

    def _change_page(self):
        self.stack.setCurrentIndex(1 if self.mode.currentData() == "postgresql" else 0)

    def _browse_sqlite(self):
        filename, _ = QFileDialog.getSaveFileName(self, "SQLite-Datenbank wählen", self.sqlite_file.text(), "SQLite (*.db *.sqlite);;Alle Dateien (*)")
        if filename:
            self.sqlite_file.setText(filename)

    def _browse_documents(self):
        folder = QFileDialog.getExistingDirectory(self, "Zentralen Dokumentordner wählen", self.document_root.text())
        if folder:
            self.document_root.setText(folder)

    def _current_config(self):
        return DatabaseConfig(
            mode=str(self.mode.currentData()),
            sqlite_file=self.sqlite_file.text().strip(),
            host=self.host.text().strip(), port=self.port.value(),
            database=self.database.text().strip(), username=self.username.text().strip(),
            password=self.password.text(), document_root=self.document_root.text().strip(),
            refresh_seconds=self.refresh_seconds.value(),
        )

    def _test_connection(self):
        config = self._current_config()
        try:
            engine = create_engine(config.url, future=True, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
        except Exception as error:
            QMessageBox.critical(self, "Verbindung fehlgeschlagen", str(error))
            return
        QMessageBox.information(self, "Verbindung erfolgreich", "Die Datenbankverbindung konnte hergestellt werden.")

    def _save(self):
        config = self._current_config()
        if config.mode == "sqlite" and not config.sqlite_file:
            QMessageBox.warning(self, "Eingabe fehlt", "Bitte eine SQLite-Datenbankdatei auswählen.")
            return
        if config.mode == "postgresql" and not all((config.host, config.database, config.username)):
            QMessageBox.warning(self, "Eingabe fehlt", "Bitte Server, Datenbank und Benutzer angeben.")
            return
        Path(config.document_root).mkdir(parents=True, exist_ok=True)
        save_database_config(config)
        QMessageBox.information(self, "Gespeichert", "Die Einstellung wird nach einem Neustart von LeipzigerFlow verwendet.")
        self.accept()
