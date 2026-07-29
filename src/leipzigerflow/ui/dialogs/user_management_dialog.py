from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from leipzigerflow.models.auth import Permission, Role, User
from leipzigerflow.services.auth_service import AuthService


class UserManagementDialog(QDialog):
    """Administrationsoberfläche für Benutzer, Rollen und Berechtigungen."""

    def __init__(self, session: Session, current_user_id: int | None = None, parent=None):
        super().__init__(parent)
        self.session = session
        self.service = AuthService(session)
        self.current_user_id = current_user_id
        self.setWindowTitle("Benutzer- und Rollenverwaltung")
        self.resize(980, 680)

        tabs = QTabWidget()
        tabs.addTab(self._build_users_tab(), "Benutzer")
        tabs.addTab(self._build_roles_tab(), "Rollen und Berechtigungen")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._load_users()
        self._load_roles()

    def _build_users_tab(self) -> QWidget:
        page = QWidget()
        self.user_list = QListWidget()
        self.user_list.currentItemChanged.connect(self._show_user)

        self.username = QLineEdit()
        self.username.setReadOnly(True)
        self.display_name = QLineEdit()
        self.email = QLineEdit()
        self.active = QCheckBox("Benutzer ist aktiv")
        self.user_roles = QListWidget()

        form = QFormLayout()
        form.addRow("Benutzername:", self.username)
        form.addRow("Anzeigename:", self.display_name)
        form.addRow("E-Mail:", self.email)
        form.addRow("", self.active)
        form.addRow("Rollen:", self.user_roles)

        new_button = QPushButton("Neu")
        new_button.clicked.connect(self._new_user)
        save_button = QPushButton("Speichern")
        save_button.clicked.connect(self._save_user)
        password_button = QPushButton("Passwort zurücksetzen")
        password_button.clicked.connect(self._reset_password)
        delete_button = QPushButton("Löschen")
        delete_button.clicked.connect(self._delete_user)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(save_button)
        actions.addWidget(password_button)
        actions.addStretch()
        actions.addWidget(delete_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(form)
        right_layout.addLayout(actions)

        splitter = QSplitter()
        splitter.addWidget(self.user_list)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    def _build_roles_tab(self) -> QWidget:
        page = QWidget()
        self.role_list = QListWidget()
        self.role_list.currentItemChanged.connect(self._show_role)

        self.role_name = QLineEdit()
        self.role_description = QLineEdit()
        self.permission_tree = QTreeWidget()
        self.permission_tree.setHeaderLabels(["Berechtigung", "Beschreibung"])
        self.permission_tree.setColumnWidth(0, 300)

        form = QFormLayout()
        form.addRow("Rollenname:", self.role_name)
        form.addRow("Beschreibung:", self.role_description)

        new_button = QPushButton("Neue Rolle")
        new_button.clicked.connect(self._new_role)
        save_button = QPushButton("Rolle speichern")
        save_button.clicked.connect(self._save_role)
        delete_button = QPushButton("Rolle löschen")
        delete_button.clicked.connect(self._delete_role)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(save_button)
        actions.addStretch()
        actions.addWidget(delete_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(form)
        right_layout.addWidget(QLabel("Berechtigungen"))
        right_layout.addWidget(self.permission_tree)
        right_layout.addLayout(actions)

        splitter = QSplitter()
        splitter.addWidget(self.role_list)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    @staticmethod
    def _checked_items(widget: QListWidget) -> list[object]:
        return [
            widget.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(widget.count())
            if widget.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _load_users(self, selected_id: int | None = None) -> None:
        self.user_list.clear()
        for user in self.service.list_users():
            text = user.display_name or user.username
            if not user.is_active:
                text += " (inaktiv)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, user.id)
            self.user_list.addItem(item)
            if user.id == selected_id:
                self.user_list.setCurrentItem(item)
        if self.user_list.currentItem() is None and self.user_list.count():
            self.user_list.setCurrentRow(0)

    def _load_roles(self, selected_id: int | None = None) -> None:
        self.role_list.clear()
        for role in self.service.list_roles():
            item = QListWidgetItem(role.name)
            item.setData(Qt.ItemDataRole.UserRole, role.id)
            self.role_list.addItem(item)
            if role.id == selected_id:
                self.role_list.setCurrentItem(item)
        if self.role_list.currentItem() is None and self.role_list.count():
            self.role_list.setCurrentRow(0)

    def _current_user(self) -> User | None:
        item = self.user_list.currentItem()
        return self.session.get(User, item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _current_role(self) -> Role | None:
        item = self.role_list.currentItem()
        return self.session.get(Role, item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _show_user(self, item: QListWidgetItem | None) -> None:
        user = self._current_user() if item else None
        self.user_roles.clear()
        if user is None:
            self.username.clear(); self.display_name.clear(); self.email.clear(); self.active.setChecked(False)
            return
        self.username.setText(user.username)
        self.display_name.setText(user.display_name)
        self.email.setText(user.email)
        self.active.setChecked(user.is_active)
        assigned = {role.id for role in user.roles}
        for role in self.service.list_roles():
            role_item = QListWidgetItem(role.name)
            role_item.setData(Qt.ItemDataRole.UserRole, role)
            role_item.setFlags(role_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            role_item.setCheckState(Qt.CheckState.Checked if role.id in assigned else Qt.CheckState.Unchecked)
            self.user_roles.addItem(role_item)

    def _new_user(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Benutzer anlegen")
        username = QLineEdit(); display = QLineEdit(); email = QLineEdit()
        password = QLineEdit(); password.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout(dialog)
        form.addRow("Benutzername:", username)
        form.addRow("Anzeigename:", display)
        form.addRow("E-Mail:", email)
        form.addRow("Startpasswort:", password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if not dialog.exec():
            return
        try:
            user = self.service.create_user(
                username.text(), password.text(), display_name=display.text(), email=email.text(),
                must_change_password=True,
            )
            self.session.commit()
            self._load_users(user.id)
        except Exception as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Benutzer anlegen", str(exc))

    def _save_user(self) -> None:
        user = self._current_user()
        if user is None:
            return
        if user.id == self.current_user_id and not self.active.isChecked():
            QMessageBox.warning(self, "Benutzer speichern", "Der aktuell angemeldete Benutzer kann nicht deaktiviert werden.")
            return
        try:
            roles = [role for role in self._checked_items(self.user_roles) if isinstance(role, Role)]
            self.service.update_user(user, display_name=self.display_name.text(), email=self.email.text(), is_active=self.active.isChecked())
            self.service.assign_roles(user, roles)
            self.session.commit()
            self._load_users(user.id)
            QMessageBox.information(self, "Benutzer speichern", "Der Benutzer wurde gespeichert.")
        except Exception as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Benutzer speichern", str(exc))

    def _reset_password(self) -> None:
        user = self._current_user()
        if user is None:
            return
        password, accepted = QInputDialog.getText(self, "Passwort zurücksetzen", "Temporäres Passwort:", QLineEdit.EchoMode.Password)
        if not accepted:
            return
        try:
            self.service.reset_password(user, password)
            self.session.commit()
            QMessageBox.information(self, "Passwort zurücksetzen", "Das Passwort wurde zurückgesetzt. Beim nächsten Login muss es geändert werden.")
        except Exception as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Passwort zurücksetzen", str(exc))

    def _delete_user(self) -> None:
        user = self._current_user()
        if user is None:
            return
        if user.id == self.current_user_id:
            QMessageBox.warning(self, "Benutzer löschen", "Der aktuell angemeldete Benutzer kann nicht gelöscht werden.")
            return
        if QMessageBox.question(self, "Benutzer löschen", f"Benutzer '{user.username}' wirklich löschen?") != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_user(user)
        self.session.commit()
        self._load_users()

    def _show_role(self, item: QListWidgetItem | None) -> None:
        role = self._current_role() if item else None
        self.role_name.setText(role.name if role else "")
        self.role_description.setText(role.description if role else "")
        self.permission_tree.clear()
        selected = {permission.id for permission in role.permissions} if role else set()
        groups: dict[str, list[Permission]] = defaultdict(list)
        for permission in self.service.list_permissions():
            groups[permission.key.split(".", 1)[0]].append(permission)
        for group_name, permissions in sorted(groups.items()):
            group = QTreeWidgetItem([group_name.capitalize(), ""])
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.permission_tree.addTopLevelItem(group)
            for permission in permissions:
                child = QTreeWidgetItem([permission.key, permission.description])
                child.setData(0, Qt.ItemDataRole.UserRole, permission)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked if permission.id in selected else Qt.CheckState.Unchecked)
                group.addChild(child)
        self.permission_tree.expandAll()

    def _new_role(self) -> None:
        self.role_list.clearSelection()
        self.role_name.clear(); self.role_description.clear()
        self._show_role(None)
        self.role_name.setFocus()

    def _save_role(self) -> None:
        try:
            role = self._current_role()
            if role is None:
                role = self.service.create_role(self.role_name.text(), self.role_description.text())
            else:
                self.service.update_role(role, name=self.role_name.text(), description=self.role_description.text())
            permissions: list[Permission] = []
            root = self.permission_tree.invisibleRootItem()
            for group_index in range(root.childCount()):
                group = root.child(group_index)
                for index in range(group.childCount()):
                    child = group.child(index)
                    permission = child.data(0, Qt.ItemDataRole.UserRole)
                    if child.checkState(0) == Qt.CheckState.Checked and isinstance(permission, Permission):
                        permissions.append(permission)
            self.service.set_role_permissions(role, permissions)
            self.session.commit()
            self._load_roles(role.id)
            self._load_users(self._current_user().id if self._current_user() else None)
            QMessageBox.information(self, "Rolle speichern", "Die Rolle wurde gespeichert.")
        except Exception as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Rolle speichern", str(exc))

    def _delete_role(self) -> None:
        role = self._current_role()
        if role is None:
            return
        if QMessageBox.question(self, "Rolle löschen", f"Rolle '{role.name}' wirklich löschen?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_role(role)
            self.session.commit()
            self._load_roles()
            self._load_users()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.warning(self, "Rolle löschen", str(exc))
