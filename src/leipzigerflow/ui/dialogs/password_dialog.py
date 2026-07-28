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

from leipzigerflow.models.auth import User
from leipzigerflow.services.auth_service import AuthService, PasswordHasher


class ChangePasswordDialog(QDialog):
    def __init__(self, session: Session, user: User, *, forced: bool = False, parent=None):
        super().__init__(parent)
        self.session = session
        self.user = user
        self.forced = forced
        self.setWindowTitle("Passwort ändern")
        self.setMinimumWidth(450)

        info = QLabel(
            "Bitte vergeben Sie ein neues Passwort mit mindestens 8 Zeichen."
            if forced
            else "Ändern Sie Ihr persönliches Passwort."
        )
        info.setWordWrap(True)

        self.old_password = QLineEdit()
        self.old_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.returnPressed.connect(self._save)

        form = QFormLayout()
        form.addRow("Bisheriges Passwort:", self.old_password)
        form.addRow("Neues Passwort:", self.new_password)
        form.addRow("Wiederholen:", self.confirm_password)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        if forced:
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def reject(self) -> None:
        if not self.forced:
            super().reject()

    def _save(self) -> None:
        if not PasswordHasher.verify(self.old_password.text(), self.user.password_hash):
            QMessageBox.warning(self, "Passwort ändern", "Das bisherige Passwort ist falsch.")
            self.old_password.clear()
            self.old_password.setFocus()
            return
        if self.new_password.text() != self.confirm_password.text():
            QMessageBox.warning(self, "Passwort ändern", "Die neuen Passwörter stimmen nicht überein.")
            return
        try:
            AuthService(self.session).change_password(self.user, self.new_password.text())
            self.session.commit()
        except ValueError as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Passwort ändern", str(exc))
            return
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Passwort ändern", str(exc))
            return
        self.accept()
