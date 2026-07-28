from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leipzigerflow.database.base import Base
from leipzigerflow.services.auth_bootstrap import seed_auth_defaults
from leipzigerflow.services.user_session import UserSession


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_user_session_is_independent_from_database_session():
    session = _session()
    result = seed_auth_defaults(
        session,
        administrator_username="admin",
        administrator_password="SicheresStartpasswort1!",
    )
    session.commit()

    app_session = UserSession()
    app_session.start(result.administrator)
    session.close()

    assert app_session.is_authenticated
    assert app_session.username == "admin"
    assert app_session.has_permission("users.manage")
    assert app_session.has_permission("PLANNING.APPLY")


def test_user_session_clear_removes_identity_and_permissions():
    session = _session()
    result = seed_auth_defaults(
        session,
        administrator_username="admin",
        administrator_password="SicheresStartpasswort1!",
    )
    app_session = UserSession()
    app_session.start(result.administrator)

    app_session.clear()

    assert not app_session.is_authenticated
    assert not app_session.has_permission("users.manage")
    assert app_session.label == ""
