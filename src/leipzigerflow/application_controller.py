from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy import func, select

from leipzigerflow.database.database import SessionLocal
from leipzigerflow.models.auth import User
from leipzigerflow.services.auth_bootstrap import seed_auth_defaults
from leipzigerflow.services.user_session import UserSession
from leipzigerflow.services.audit_context import set_user, clear_user
from leipzigerflow.ui.dialogs.initial_admin_dialog import InitialAdminDialog
from leipzigerflow.ui.dialogs.login_dialog import LoginDialog
from leipzigerflow.ui.dialogs.password_dialog import ChangePasswordDialog
from leipzigerflow.ui.main_window import MainWindow


class ApplicationController(QObject):
    """Steuert Ersteinrichtung, Anmeldung, Hauptfenster und Benutzerwechsel."""

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.user_session = UserSession()
        self.main_window: MainWindow | None = None

    def start(self) -> bool:
        if not self._ensure_initial_user():
            return False
        return self._login_and_show_main_window()

    def _ensure_initial_user(self) -> bool:
        session = SessionLocal()
        try:
            seed_auth_defaults(session)
            session.commit()
            user_count = session.scalar(select(func.count()).select_from(User)) or 0
            if user_count:
                return True
            return InitialAdminDialog(session).exec() == QDialog.DialogCode.Accepted
        finally:
            session.close()

    def _login_and_show_main_window(self) -> bool:
        session = SessionLocal()
        try:
            dialog = LoginDialog(session)
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.authenticated_user is None:
                return False
            user = dialog.authenticated_user
            self.user_session.start(user)
            set_user(user.id, user.username, user.display_name)
            if user.must_change_password:
                if ChangePasswordDialog(session, user, forced=True).exec() != QDialog.DialogCode.Accepted:
                    self.user_session.clear()
                    return False
                self.user_session.start(user)
        finally:
            session.close()

        self.main_window = MainWindow(self.user_session)
        self.main_window.logout_requested.connect(self._switch_user)
        self.main_window.show()
        return True

    def _switch_user(self) -> None:
        previous_window = self.main_window
        if previous_window is not None:
            previous_window.window_manager.close_all(preserve_workspace=True)
            previous_window.hide()
        self.main_window = None
        self.user_session.clear()
        clear_user()

        if self._login_and_show_main_window():
            if previous_window is not None:
                previous_window.close()
                previous_window.deleteLater()
            return

        if previous_window is not None:
            previous_window.close()
            previous_window.deleteLater()
        self.app.quit()
