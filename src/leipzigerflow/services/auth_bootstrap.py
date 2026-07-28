from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from leipzigerflow.models.auth import Role, User
from leipzigerflow.services.auth_service import AuthService


DEFAULT_PERMISSIONS: dict[str, str] = {
    "planning.view": "Plantafel und Disposition ansehen",
    "planning.edit": "Touren und Zuordnungen bearbeiten",
    "planning.apply": "Automatische Disposition übernehmen",
    "orders.view": "Transportaufträge ansehen",
    "orders.edit": "Transportaufträge bearbeiten",
    "customers.view": "Kunden ansehen",
    "customers.edit": "Kunden bearbeiten",
    "fleet.view": "Fahrzeuge, Trailer und Fahrer ansehen",
    "fleet.edit": "Fahrzeuge, Trailer und Fahrer bearbeiten",
    "users.manage": "Benutzer, Rollen und Berechtigungen verwalten",
    "settings.edit": "Programmeinstellungen bearbeiten",
    "api.manage": "API-Verbindungen konfigurieren",
    "ai.use": "KI-Assistent verwenden",
}

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "Administrator": tuple(DEFAULT_PERMISSIONS),
    "Disposition": (
        "planning.view",
        "planning.edit",
        "planning.apply",
        "orders.view",
        "orders.edit",
        "customers.view",
        "fleet.view",
        "fleet.edit",
        "ai.use",
    ),
    "Vertrieb": (
        "planning.view",
        "orders.view",
        "orders.edit",
        "customers.view",
        "customers.edit",
    ),
    "Lager": (
        "planning.view",
        "orders.view",
        "fleet.view",
    ),
    "Geschäftsführung": (
        "planning.view",
        "orders.view",
        "customers.view",
        "fleet.view",
        "ai.use",
    ),
}


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    roles: dict[str, Role]
    administrator: User | None


def seed_auth_defaults(
    session: Session,
    *,
    administrator_username: str | None = None,
    administrator_password: str | None = None,
    administrator_display_name: str = "Administrator",
) -> BootstrapResult:
    """Legt Standardrechte/-rollen idempotent an und optional den ersten Admin.

    Ein Administrator wird nur erzeugt, wenn Benutzername und Passwort explizit
    übergeben werden. Dadurch existiert kein fest eingebautes Standardpasswort.
    """
    service = AuthService(session)
    permissions = {
        key: service.create_permission(key, description)
        for key, description in DEFAULT_PERMISSIONS.items()
    }
    roles: dict[str, Role] = {}
    for role_name, permission_keys in DEFAULT_ROLE_PERMISSIONS.items():
        role = service.create_role(role_name)
        for permission_key in permission_keys:
            service.grant_permission(role, permissions[permission_key])
        roles[role_name] = role

    administrator = None
    if administrator_username is not None or administrator_password is not None:
        if not administrator_username or not administrator_password:
            raise ValueError("Für den Administrator werden Benutzername und Passwort benötigt.")
        administrator = service.get_user(administrator_username)
        if administrator is None:
            administrator = service.create_user(
                administrator_username,
                administrator_password,
                display_name=administrator_display_name,
                must_change_password=True,
            )
        service.assign_role(administrator, roles["Administrator"])

    session.flush()
    return BootstrapResult(roles=roles, administrator=administrator)
