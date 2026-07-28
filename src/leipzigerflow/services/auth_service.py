from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from leipzigerflow.models.auth import Permission, Role, User


class AuthenticationError(ValueError):
    """Anmeldung fehlgeschlagen, ohne interne Details preiszugeben."""


class PasswordHasher:
    """Versioniertes Passwort-Hashing ausschließlich mit Python-Standardbibliothek."""

    algorithm = "scrypt"
    n = 2**14
    r = 8
    p = 1
    salt_bytes = 16
    key_length = 32

    @classmethod
    def hash(cls, password: str) -> str:
        cls._validate(password)
        salt = secrets.token_bytes(cls.salt_bytes)
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=cls.n, r=cls.r, p=cls.p, dklen=cls.key_length
        )
        return "$".join(
            (
                cls.algorithm,
                str(cls.n),
                str(cls.r),
                str(cls.p),
                base64.urlsafe_b64encode(salt).decode("ascii"),
                base64.urlsafe_b64encode(digest).decode("ascii"),
            )
        )

    @classmethod
    def verify(cls, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
            if algorithm != cls.algorithm:
                return False
            salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
            expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(expected),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _validate(password: str) -> None:
        if len(password) < 8:
            raise ValueError("Das Passwort muss mindestens 8 Zeichen lang sein.")


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def create_user(
        self,
        username: str,
        password: str,
        *,
        display_name: str = "",
        email: str = "",
        is_active: bool = True,
        must_change_password: bool = False,
    ) -> User:
        normalized = self._normalize_username(username)
        if self.get_user(normalized) is not None:
            raise ValueError("Dieser Benutzername ist bereits vergeben.")
        user = User(
            username=normalized,
            password_hash=PasswordHasher.hash(password),
            display_name=display_name.strip(),
            email=email.strip(),
            is_active=is_active,
            must_change_password=must_change_password,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def get_user(self, username: str) -> User | None:
        normalized = self._normalize_username(username)
        return self.session.scalar(select(User).where(User.username == normalized))

    def authenticate(self, username: str, password: str) -> User:
        user = self.get_user(username)
        if user is None or not user.is_active or not PasswordHasher.verify(password, user.password_hash):
            raise AuthenticationError("Benutzername oder Passwort ist ungültig.")
        user.last_login = datetime.now()
        self.session.flush()
        return user

    def change_password(self, user: User, new_password: str, *, require_change: bool = False) -> None:
        user.password_hash = PasswordHasher.hash(new_password)
        user.must_change_password = require_change
        self.session.flush()

    def create_role(self, name: str, description: str = "") -> Role:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Bitte einen Rollennamen eingeben.")
        existing = self.session.scalar(select(Role).where(Role.name == normalized))
        if existing is not None:
            return existing
        role = Role(name=normalized, description=description.strip())
        self.session.add(role)
        self.session.flush()
        return role

    def create_permission(self, key: str, description: str = "") -> Permission:
        normalized = key.strip().lower()
        if not normalized or "." not in normalized:
            raise ValueError("Berechtigungen müssen dem Muster 'bereich.aktion' entsprechen.")
        existing = self.session.scalar(select(Permission).where(Permission.key == normalized))
        if existing is not None:
            return existing
        permission = Permission(key=normalized, description=description.strip())
        self.session.add(permission)
        self.session.flush()
        return permission

    def assign_role(self, user: User, role: Role) -> None:
        if role not in user.roles:
            user.roles.append(role)
            self.session.flush()

    def grant_permission(self, role: Role, permission: Permission) -> None:
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.session.flush()

    @staticmethod
    def has_permission(user: User, permission_key: str) -> bool:
        return user.is_active and user.has_permission(permission_key)

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = username.strip().lower()
        if not normalized:
            raise ValueError("Bitte einen Benutzernamen eingeben.")
        if any(character.isspace() for character in normalized):
            raise ValueError("Der Benutzername darf keine Leerzeichen enthalten.")
        return normalized
