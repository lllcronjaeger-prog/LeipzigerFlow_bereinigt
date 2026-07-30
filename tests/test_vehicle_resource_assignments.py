from datetime import date, datetime, time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.models import *
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.vehicle_resource_assignment import VehicleResourceAssignment
from leipzigerflow.services.tour_resource_assignment_service import TourResourceAssignmentService
from leipzigerflow.services.tour_service import TourService


def test_driver_is_propagated_for_selected_period_and_stored_as_vehicle_assignment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vehicle = Vehicle(vehicle_number="1", license_plate="L-LL 1", home_base="Leipzig")
        driver = Driver(match_code="D1", first_name="Max", last_name="Test", work_model="MO-FR")
        first = Tour(tour_number="T1", tour_date=date(2026, 8, 3), planned_start_time=time(6), vehicle=vehicle)
        second = Tour(tour_number="T2", tour_date=date(2026, 8, 4), planned_start_time=time(7), vehicle=vehicle)
        third = Tour(tour_number="T3", tour_date=date(2026, 8, 5), planned_start_time=time(8), vehicle=vehicle)
        session.add_all([driver, first, second, third])
        session.commit()

        TourResourceAssignmentService(session).assign_driver_segments(
            first,
            [{"driver_id": driver.id, "starts_at": datetime(2026, 8, 3, 6), "ends_at": datetime(2026, 8, 3, 14)}],
            propagate_last=True,
            valid_until=date(2026, 8, 4),
        )

        assert second.driver_id == driver.id
        assert len(second.driver_assignments) == 1
        assert third.driver_id is None
        assignment = session.scalar(select(VehicleResourceAssignment))
        assert assignment.valid_from == date(2026, 8, 4)
        assert assignment.valid_until == date(2026, 8, 4)


def test_duplicate_vehicle_tours_are_merged_into_one_tour():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vehicle = Vehicle(vehicle_number="1", license_plate="L-LL 2")
        first = Tour(tour_number="A", tour_date=date(2026, 8, 3), vehicle=vehicle)
        second = Tour(tour_number="B", tour_date=date(2026, 8, 3), vehicle=vehicle)
        session.add_all([first, second])
        session.commit()

        assert TourService(session).consolidate_duplicate_vehicle_tours() == 1
        tours = list(session.scalars(select(Tour)))
        assert len(tours) == 1
        assert tours[0].vehicle_id == vehicle.id
