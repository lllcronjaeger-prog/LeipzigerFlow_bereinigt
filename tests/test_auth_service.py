from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leipzigerflow.database.base import Base
from leipzigerflow.models.auth import Permission, Role, User
from leipzigerflow.services.auth_service import AuthenticationError, AuthService, PasswordHasher


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_passwords_are_salted_and_verifiable():
    first = PasswordHasher.hash("SicheresPasswort1!")
    second = PasswordHasher.hash("SicheresPasswort1!")
    assert first != second
    assert PasswordHasher.verify("SicheresPasswort1!", first)
    assert not PasswordHasher.verify("Falsch", first)


def test_user_authentication_and_last_login():
    session = _session()
    service = AuthService(session)
    user = service.create_user("Dispo", "SicheresPasswort1!", display_name="Disposition")
    session.commit()

    authenticated = service.authenticate("DISPO", "SicheresPasswort1!")
    assert authenticated.id == user.id
    assert authenticated.last_login is not None

    try:
        service.authenticate("dispo", "falsch")
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Falsches Passwort wurde akzeptiert.")


def test_roles_and_permissions_are_assigned_idempotently():
    session = _session()
    service = AuthService(session)
    user = service.create_user("lager", "SicheresPasswort1!")
    role = service.create_role("Lager")
    permission = service.create_permission("planning.view", "Plantafel ansehen")

    service.assign_role(user, role)
    service.assign_role(user, role)
    service.grant_permission(role, permission)
    service.grant_permission(role, permission)
    session.commit()

    assert len(user.roles) == 1
    assert len(role.permissions) == 1
    assert service.has_permission(user, "PLANNING.VIEW")
    assert not service.has_permission(user, "planning.apply")


def test_auth_bootstrap_creates_defaults_idempotently():
    from sqlalchemy import func, select

    from leipzigerflow.services.auth_bootstrap import (
        DEFAULT_PERMISSIONS,
        DEFAULT_ROLE_PERMISSIONS,
        seed_auth_defaults,
    )

    session = _session()
    first = seed_auth_defaults(
        session,
        administrator_username="admin",
        administrator_password="SicheresStartpasswort1!",
    )
    second = seed_auth_defaults(
        session,
        administrator_username="admin",
        administrator_password="SicheresStartpasswort1!",
    )
    session.commit()

    assert first.administrator is not None
    assert second.administrator is not None
    assert first.administrator.id == second.administrator.id
    assert first.administrator.must_change_password
    assert first.administrator.has_permission("users.manage")
    assert session.scalar(select(func.count()).select_from(User)) == 1
    assert session.scalar(select(func.count()).select_from(Role)) == len(DEFAULT_ROLE_PERMISSIONS)
    assert session.scalar(select(func.count()).select_from(Permission)) == len(DEFAULT_PERMISSIONS)


def test_user_administration_and_password_reset():
    session = _session()
    service = AuthService(session)
    user = service.create_user("fahrer", "SicheresPasswort1!")
    role = service.create_role("Fahrer")
    service.assign_roles(user, [role])
    service.update_user(user, display_name="Max Fahrer", email="max@example.de", is_active=False)
    service.reset_password(user, "NeuesPasswort1!")
    session.commit()

    assert user.display_name == "Max Fahrer"
    assert user.email == "max@example.de"
    assert not user.is_active
    assert user.must_change_password
    assert [assigned.name for assigned in user.roles] == ["Fahrer"]
    assert PasswordHasher.verify("NeuesPasswort1!", user.password_hash)


def test_role_permissions_can_be_replaced_and_role_with_users_cannot_be_deleted():
    session = _session()
    service = AuthService(session)
    user = service.create_user("dispo2", "SicheresPasswort1!")
    role = service.create_role("Disposition 2")
    first = service.create_permission("orders.view", "Aufträge ansehen")
    second = service.create_permission("planning.view", "Planung ansehen")
    service.assign_role(user, role)
    service.set_role_permissions(role, [first, second])
    service.set_role_permissions(role, [second])

    assert [permission.key for permission in role.permissions] == ["planning.view"]
    try:
        service.delete_role(role)
    except ValueError:
        pass
    else:
        raise AssertionError("Zugewiesene Rolle wurde gelöscht.")
