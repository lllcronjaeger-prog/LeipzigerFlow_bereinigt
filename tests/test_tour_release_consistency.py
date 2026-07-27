from datetime import date

from sqlalchemy import create_engine, select
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
    return Session(engine, expire_on_commit=False, autoflush=False)


def add_tour_with_orders(session: Session, count: int = 3) -> Tour:
    customer = Customer(name="Testkunde")
    loading = Location(
        location_type=LocationType.CUSTOMER,
        name="Start",
        postal_code="76133",
        city="Karlsruhe",
    )
    unloading = Location(
        location_type=LocationType.CUSTOMER,
        name="Ziel",
        postal_code="76726",
        city="Germersheim",
    )
    session.add_all([customer, loading, unloading])
    session.flush()

    tour = Tour(
        tour_number="T-2026-00001",
        tour_date=date(2026, 7, 28),
        status="Geplant",
    )
    for index in range(1, count + 1):
        order = TransportOrder(
            order_number=f"LF-2026-{index:06d}",
            customer_id=customer.id,
            loading_location_id=loading.id,
            unloading_location_id=unloading.id,
            loading_date=tour.tour_date,
            unloading_date=tour.tour_date,
            status="Geplant",
        )
        tour.positions.append(TourPosition(position=index, transport_order=order))
    session.add(tour)
    session.commit()
    return tour


def test_released_order_disappears_from_loaded_relationship_without_ghost_position():
    with make_session() as session:
        tour = add_tour_with_orders(session)
        removed_order_id = tour.positions[1].transport_order_id

        refreshed = TourService(session).release_orders(tour, [removed_order_id])

        assert [position.position for position in refreshed.positions] == [1, 2]
        assert all(position.position > 0 for position in refreshed.positions)
        assert removed_order_id not in {
            position.transport_order_id for position in refreshed.positions
        }


def test_released_order_is_open_and_no_temporary_position_remains_in_database():
    with make_session() as session:
        tour = add_tour_with_orders(session)
        removed_order = tour.positions[0].transport_order

        TourService(session).release_orders(tour, [removed_order.id])

        session.refresh(removed_order)
        assert removed_order.status == "Neu"
        stored_positions = list(session.scalars(select(TourPosition)))
        assert [position.position for position in stored_positions] == [1, 2]
        assert all(position.position > 0 for position in stored_positions)
