from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.services.tour_service import TourService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_tour_with_order(session: Session, order_status: str = "Geplant", tour_status: str = "Geplant") -> Tour:
    customer = Customer(name="Testkunde")
    loading = Location(location_type=LocationType.CUSTOMER, name="Start", postal_code="76133", city="Karlsruhe")
    unloading = Location(location_type=LocationType.CUSTOMER, name="Ziel", postal_code="76726", city="Germersheim")
    session.add_all([customer, loading, unloading])
    session.flush()
    order = TransportOrder(
        order_number="A-1",
        customer_id=customer.id,
        loading_location_id=loading.id,
        unloading_location_id=unloading.id,
        loading_date=date(2026, 7, 23),
        unloading_date=date(2026, 7, 23),
        status=order_status,
    )
    tour = Tour(tour_number="T-2026-00001", tour_date=date(2026, 7, 23), status=tour_status)
    tour.positions.append(TourPosition(position=1, transport_order=order))
    session.add(tour)
    session.commit()
    return tour


def test_completed_tour_is_recognized_as_archived():
    with make_session() as session:
        tour = add_tour_with_order(session, order_status="Erledigt", tour_status="Abgeschlossen")
        assert TourService.is_archived(tour)


def test_all_completed_orders_automatically_close_tour():
    with make_session() as session:
        tour = add_tour_with_order(session, order_status="Erledigt", tour_status="Geplant")
        service = TourService(session)
        assert service.synchronize_completed_tours() == 1
        refreshed = service.get(tour.id)
        assert refreshed is not None
        assert refreshed.status == "Abgeschlossen"
        assert service.is_archived(refreshed)


def test_reactivating_archived_tour_reactivates_orders():
    with make_session() as session:
        tour = add_tour_with_order(session, order_status="Erledigt", tour_status="Abgeschlossen")
        service = TourService(session)
        refreshed = service.get(tour.id)
        service.change_status(refreshed, "Geplant")
        reactivated = service.get(tour.id)
        assert reactivated.status == "Geplant"
        assert not service.is_archived(reactivated)
        assert reactivated.positions[0].transport_order.status == "Geplant"
