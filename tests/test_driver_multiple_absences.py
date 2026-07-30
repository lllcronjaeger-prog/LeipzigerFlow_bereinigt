from datetime import date, datetime
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.models.driver import Driver
from leipzigerflow.services.driver_service import DriverService
from leipzigerflow.services.rotation_manager import RotationManager


def test_driver_can_store_multiple_planned_absences():
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        driver = Driver(match_code="D1", first_name="Max", last_name="Muster", active=True)
        session.add(driver); session.commit()
        drafts = [
            SimpleNamespace(starts_at=datetime(2026, 8, 3), ends_at=datetime(2026, 8, 7, 23, 59), reason="Urlaub", remarks="", active=True),
            SimpleNamespace(starts_at=datetime(2026, 9, 1), ends_at=datetime(2026, 9, 2, 23, 59), reason="Schulung", remarks="ADR", active=True),
        ]
        DriverService(session).replace_absences(driver, drafts)
        assert len(driver.absences) == 2
        assert RotationManager().status(driver, date(2026, 8, 5)).available is False
        assert RotationManager().status(driver, date(2026, 8, 5)).reason == "Urlaub"
