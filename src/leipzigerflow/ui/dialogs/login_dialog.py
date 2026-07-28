from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from leipzigerflow.models.auth import User
from leipzigerflow.services.auth_service import AuthenticationError, AuthService


class LoginDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.authenticated_user: User | None = None
        self.setWindowTitle("Anmeldung · LeipzigerFlow")
        self.setModal(True)
        self.setMinimumWidth(430)

        title = QLabel("LeipzigerFlow anmelden")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Benutzername")
        self.username_edit.setClearButtonEnabled(True)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Passwort")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self._authenticate)

        self.show_password = QCheckBox("Passwort anzeigen")
        self.show_password.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b91c1c;")

        form = QFormLayout()
        form.addRow("Benutzername:", self.username_edit)
        form.addRow("Passwort:", self.password_edit)
        form.addRow("", self.show_password)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.login_button = QPushButton("Anmelden")
        self.login_button.setDefault(True)
        buttons.addButton(self.login_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.login_button.clicked.connect(self._authenticate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)
        self.username_edit.setFocus()

    def _authenticate(self) -> None:
        self.error_label.clear()
        try:
            user = AuthService(self.session).authenticate(
                self.username_edit.text(), self.password_edit.text()
            )
            self.session.commit()
        except (AuthenticationError, ValueError) as exc:
            self.session.rollback()
            self.password_edit.clear()
            self.password_edit.setFocus()
            self.error_label.setText(str(exc))
            return
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Anmeldung nicht möglich", str(exc))
            return
        self.authenticated_user = user
        self.accept()
