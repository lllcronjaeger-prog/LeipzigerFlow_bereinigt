from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leipzigerflow.ai.router import AiQueryRouter
from leipzigerflow.database.base import Base
from leipzigerflow.models.vehicle import Vehicle


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_router_answers_vehicle_count_without_language_model():
    session = _session()
    session.add_all(
        [
            Vehicle(vehicle_number="1", license_plate="KA-A 1", active=True),
            Vehicle(vehicle_number="2", license_plate="KA-A 2", active=True),
            Vehicle(vehicle_number="3", license_plate="KA-A 3", active=False),
        ]
    )
    session.commit()

    result = AiQueryRouter(session).answer("Wie viele Fahrzeuge habe ich?")

    assert result is not None
    assert "2 aktive Fahrzeuge" in result.text
    assert "3 insgesamt" in result.text


def test_router_leaves_analysis_questions_to_language_model():
    session = _session()
    result = AiQueryRouter(session).answer("Warum sind meine Touren kritisch?")
    assert result is None


def test_router_answers_open_tours_with_status_breakdown_without_language_model():
    from datetime import date
    from leipzigerflow.models.tour import Tour

    session = _session()
    session.add_all(
        [
            Tour(tour_number="T-1", tour_date=date(2026, 7, 29), status="Geplant"),
            Tour(tour_number="T-2", tour_date=date(2026, 7, 29), status="Geplant"),
            Tour(tour_number="T-3", tour_date=date(2026, 7, 29), status="Unterwegs"),
            Tour(tour_number="T-4", tour_date=date(2026, 7, 29), status="Abgeschlossen"),
            Tour(tour_number="T-5", tour_date=date(2026, 7, 29), status="Storniert"),
        ]
    )
    session.commit()

    result = AiQueryRouter(session).answer("Welche Touren sind offen?")

    assert result is not None
    assert "3 offene Touren" in result.text
    assert "2 „Geplant“" in result.text
    assert "1 „Unterwegs“" in result.text
    assert "nicht als offen gezählt" in result.text


def test_router_answers_tours_without_driver_only_for_open_tours():
    from datetime import date
    from leipzigerflow.models.tour import Tour

    session = _session()
    session.add_all(
        [
            Tour(tour_number="T-1", tour_date=date(2026, 7, 29), status="Geplant", driver_id=None),
            Tour(tour_number="T-2", tour_date=date(2026, 7, 29), status="Abgeschlossen", driver_id=None),
        ]
    )
    session.commit()

    result = AiQueryRouter(session).answer("Wie viele offene Touren sind ohne Fahrer?")

    assert result is not None
    assert result.text == "Aktuell ist 1 offene Tour ohne Fahrer."


def test_router_answers_planned_tours_without_language_model():
    from datetime import date
    from leipzigerflow.models.tour import Tour

    session = _session()
    session.add_all(
        [
            Tour(tour_number="T-1", tour_date=date(2026, 7, 29), status="Geplant"),
            Tour(tour_number="T-2", tour_date=date(2026, 7, 29), status="Unterwegs"),
        ]
    )
    session.commit()

    result = AiQueryRouter(session).answer("Welche Touren sind geplant?")

    assert result is not None
    assert "1 Tour" in result.text
    assert "„Geplant“" in result.text
