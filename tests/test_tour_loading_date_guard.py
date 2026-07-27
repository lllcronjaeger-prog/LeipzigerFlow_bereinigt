from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.services.tour_service import TourService, TourValidationError


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def make_order(session: Session, loading_date: date, number: str) -> TransportOrder:
    customer = session.query(Customer).first()
    if customer is None:
        customer = Customer(name="Testkunde")
        loading = Location(location_type=LocationType.CUSTOMER, name="Start", postal_code="76133", city="Karlsruhe")
        unloading = Location(location_type=LocationType.CUSTOMER, name="Ziel", postal_code="76726", city="Germersheim")
        session.add_all([customer, loading, unloading])
        session.flush()
    else:
        loading, unloading = session.query(Location).all()[:2]
    order = TransportOrder(
        order_number=number,
        customer_id=customer.id,
        loading_location_id=loading.id,
        unloading_location_id=unloading.id,
        loading_date=loading_date,
        unloading_date=loading_date,
        status="Neu",
    )
    session.add(order)
    session.commit()
    return order


def test_order_with_different_loading_date_cannot_be_added_to_daily_tour():
    with make_session() as session:
        tour = Tour(tour_number="T-1", tour_date=date(2026, 7, 24), status="Geplant")
        session.add(tour)
        session.commit()
        order = make_order(session, date(2026, 7, 25), "A-25")
        with pytest.raises(TourValidationError, match="eigene Tagestour"):
            TourService(session).add_order(tour, order)


def test_order_with_same_loading_date_can_be_added_to_daily_tour():
    with make_session() as session:
        tour = Tour(tour_number="T-1", tour_date=date(2026, 7, 24), status="Geplant")
        session.add(tour)
        session.commit()
        order = make_order(session, date(2026, 7, 24), "A-24")
        updated = TourService(session).add_order(tour, order)
        assert [position.transport_order_id for position in updated.positions] == [order.id]
