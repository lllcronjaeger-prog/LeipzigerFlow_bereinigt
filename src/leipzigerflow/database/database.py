from leipzigerflow.database.base import Base
from leipzigerflow.database.session import DATABASE_URL, SessionLocal, engine


def create_database():
    """Erzeugt alle bekannten Tabellen in der aktiv konfigurierten Datenbank."""
    Base.metadata.create_all(bind=engine)
