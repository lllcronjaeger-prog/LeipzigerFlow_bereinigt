from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from leipzigerflow.services.auth_bootstrap import seed_auth_defaults


class InitialAdminDialog(QDialog):
    """Sichere Ersteinrichtung, wenn noch kein Benutzer existiert."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("LeipzigerFlow einrichten")
        self.setMinimumWidth(480)

        info = QLabel(
            "Es existiert noch kein Benutzer. Legen Sie jetzt den ersten Administrator an."
        )
        info.setWordWrap(True)
        self.username = QLineEdit("admin")
        self.display_name = QLineEdit("Administrator")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.returnPressed.connect(self._create)

        form = QFormLayout()
        form.addRow("Benutzername:", self.username)
        form.addRow("Anzeigename:", self.display_name)
        form.addRow("Passwort:", self.password)
        form.addRow("Wiederholen:", self.confirm)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Administrator anlegen")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _create(self) -> None:
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Ersteinrichtung", "Die Passwörter stimmen nicht überein.")
            return
        try:
            seed_auth_defaults(
                self.session,
                administrator_username=self.username.text(),
                administrator_password=self.password.text(),
                administrator_display_name=self.display_name.text(),
            )
            self.session.commit()
        except ValueError as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Ersteinrichtung", str(exc))
            return
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Ersteinrichtung", str(exc))
            return
        self.accept()
