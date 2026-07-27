from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.services.operations_dashboard import OperationsDashboardService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_snapshot_counts_available_resources_and_absence():
    today = date(2026, 7, 21)
    with make_session() as session:
        session.add_all(
            [
                Driver(first_name="Anna", last_name="Frei", active=True),
                Driver(
                    first_name="Max",
                    last_name="Urlaub",
                    active=True,
                    absence_from=today,
                    absence_until=today + timedelta(days=3),
                    absence_reason="Urlaub",
                ),
                Vehicle(vehicle_number="1", license_plate="L-A 1", status="Frei", active=True),
                Vehicle(vehicle_number="2", license_plate="L-A 2", status="Werkstatt", active=True),
                Trailer(
                    trailer_number="T1",
                    license_plate="L-T 1",
                    trailer_type="Plane",
                    status="Frei",
                    active=True,
                ),
            ]
        )
        session.commit()

        snapshot = OperationsDashboardService().build_snapshot(session, today)

        assert snapshot.active_drivers == 2
        assert snapshot.available_drivers == 1
        assert snapshot.absent_drivers == 1
        assert snapshot.available_vehicles == 1
        assert snapshot.workshop_vehicles == 1
        assert snapshot.available_trailers == 1


def test_snapshot_detects_critical_mega_order_and_due_dates():
    today = date(2026, 7, 21)
    with make_session() as session:
        customer = Customer(name="Testkunde")
        loading = Location(location_type=LocationType.CUSTOMER, name="Start", postal_code="04103", city="Leipzig")
        unloading = Location(location_type=LocationType.CUSTOMER, name="Ziel", postal_code="01067", city="Dresden")
        session.add_all([customer, loading, unloading])
        session.flush()
        session.add(
            TransportOrder(
                order_number="A-1",
                customer_id=customer.id,
                loading_location_id=loading.id,
                unloading_location_id=unloading.id,
                loading_date=today,
                unloading_date=today,
                status="Neu",
                remarks="",
                required_trailer_type="Mega-Plane",
            )
        )
        session.add(
            Vehicle(
                vehicle_number="1",
                license_plate="L-A 1",
                status="Frei",
                active=True,
                hu_date=today + timedelta(days=5),
            )
        )
        session.add(
            Trailer(
                trailer_number="T1",
                license_plate="L-T 1",
                trailer_type="Plane",
                status="Frei",
                active=True,
            )
        )
        session.commit()

        snapshot = OperationsDashboardService().build_snapshot(session, today)

        assert snapshot.open_orders == 1
        assert snapshot.critical_orders == 1
        assert snapshot.mega_orders == 1
        assert any("Mega-Aufträge" in warning.title for warning in snapshot.warnings)
        assert any("HU läuft" in warning.detail for warning in snapshot.warnings)


def test_underway_orders_are_not_listed_as_open():
    today = date(2026, 7, 21)
    with make_session() as session:
        customer = Customer(name="Testkunde")
        loading = Location(
            location_type=LocationType.CUSTOMER,
            name="Start",
            postal_code="04103",
            city="Leipzig",
        )
        unloading = Location(
            location_type=LocationType.CUSTOMER,
            name="Ziel",
            postal_code="01067",
            city="Dresden",
        )
        session.add_all([customer, loading, unloading])
        session.flush()

        order_with_status = TransportOrder(
            order_number="A-UNTERWEGS",
            customer_id=customer.id,
            loading_location_id=loading.id,
            unloading_location_id=unloading.id,
            loading_date=today,
            unloading_date=today,
            status="Unterwegs",
        )
        order_in_underway_tour = TransportOrder(
            order_number="A-TOUR",
            customer_id=customer.id,
            loading_location_id=loading.id,
            unloading_location_id=unloading.id,
            loading_date=today,
            unloading_date=today,
            status="Geplant",
        )
        open_order = TransportOrder(
            order_number="A-OFFEN",
            customer_id=customer.id,
            loading_location_id=loading.id,
            unloading_location_id=unloading.id,
            loading_date=today,
            unloading_date=today,
            status="Neu",
        )
        session.add_all([order_with_status, order_in_underway_tour, open_order])
        session.flush()

        tour = Tour(tour_number="T-1", tour_date=today, status="Unterwegs")
        session.add(tour)
        session.flush()
        session.add(
            TourPosition(
                tour_id=tour.id,
                transport_order_id=order_in_underway_tour.id,
                position=1,
            )
        )
        session.commit()

        snapshot = OperationsDashboardService().build_snapshot(session, today)

        assert snapshot.open_orders == 1
        assert [order.order_number for order in snapshot.open_order_rows] == ["A-OFFEN"]
        assert snapshot.critical_orders == 1


def test_planned_orders_are_not_open_or_critical():
    today = date(2026, 7, 21)
    with make_session() as session:
        customer = Customer(name="Testkunde")
        loading = Location(location_type=LocationType.CUSTOMER, name="Start", postal_code="04103", city="Leipzig")
        unloading = Location(location_type=LocationType.CUSTOMER, name="Ziel", postal_code="01067", city="Dresden")
        session.add_all([customer, loading, unloading])
        session.flush()
        planned = TransportOrder(
            order_number="A-GEPLANT", customer_id=customer.id,
            loading_location_id=loading.id, unloading_location_id=unloading.id,
            loading_date=today, unloading_date=today, status="Geplant",
            required_trailer_type="Mega-Plane",
        )
        session.add(planned)
        session.commit()
        snapshot = OperationsDashboardService().build_snapshot(session, today)
        assert snapshot.open_orders == 0
        assert snapshot.critical_orders == 0
        assert snapshot.mega_orders == 0
        assert snapshot.open_order_rows == []


def test_snapshot_reports_own_fleet_coverage_and_recommendations():
    today = date(2026, 7, 21)
    with make_session() as session:
        customer = Customer(name="Testkunde")
        loading = Location(location_type=LocationType.CUSTOMER, name="Start", postal_code="76133", city="Karlsruhe")
        unloading = Location(location_type=LocationType.CUSTOMER, name="Ziel", postal_code="76726", city="Germersheim")
        session.add_all([customer, loading, unloading])
        session.flush()
        planned = TransportOrder(
            order_number="EIGEN-1", customer_id=customer.id,
            loading_location_id=loading.id, unloading_location_id=unloading.id,
            loading_date=today, unloading_date=today, status="Geplant",
            dispatch_priority="Eigenfuhrpark bevorzugt",
        )
        open_order = TransportOrder(
            order_number="EIGEN-2", customer_id=customer.id,
            loading_location_id=loading.id, unloading_location_id=unloading.id,
            loading_date=today, unloading_date=today, status="Neu",
            dispatch_priority="Eigenfuhrpark bevorzugt",
        )
        sale_order = TransportOrder(
            order_number="VERKAUF-1", customer_id=customer.id,
            loading_location_id=loading.id, unloading_location_id=unloading.id,
            loading_date=today, unloading_date=today, status="Neu",
            dispatch_priority="Verkauf bevorzugt",
        )
        session.add_all([planned, open_order, sale_order])
        session.flush()
        tour = Tour(tour_number="T-PLAN", tour_date=today, status="Geplant")
        session.add(tour)
        session.flush()
        session.add(TourPosition(tour_id=tour.id, transport_order_id=planned.id, position=1))
        session.commit()

        snapshot = OperationsDashboardService().build_snapshot(session, today)

        assert snapshot.own_fleet_orders_today == 2
        assert snapshot.own_fleet_planned_today == 1
        assert snapshot.sales_orders_open == 1
        assert snapshot.planning_quality == 40  # 50 % Deckung minus 10 % für unvollständige Tour
        assert any("Eigenfuhrpark" in item.title for item in snapshot.recommendations)
        assert any("Verkaufsauftrag" in item.title for item in snapshot.recommendations)
