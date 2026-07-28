from __future__ import annotations

from dataclasses import dataclass, field

from leipzigerflow.models.auth import User


@dataclass(slots=True)
class UserSession:
    """Von der SQLAlchemy-Sitzung unabhängiger Anmeldekontext der Anwendung."""

    user_id: int | None = None
    username: str = ""
    display_name: str = ""
    must_change_password: bool = False
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def label(self) -> str:
        return self.display_name or self.username

    def start(self, user: User) -> None:
        self.user_id = user.id
        self.username = user.username
        self.display_name = user.display_name
        self.must_change_password = user.must_change_password
        self.permissions = frozenset(
            permission.key.lower()
            for role in user.roles
            for permission in role.permissions
        )

    def clear(self) -> None:
        self.user_id = None
        self.username = ""
        self.display_name = ""
        self.must_change_password = False
        self.permissions = frozenset()

    def has_permission(self, permission_key: str) -> bool:
        return self.is_authenticated and permission_key.strip().lower() in self.permissions
