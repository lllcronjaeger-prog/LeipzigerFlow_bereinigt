from datetime import date, datetime, time
from types import SimpleNamespace

from leipzigerflow.planner.engine.availability import ResourceAvailabilityEngine
from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.state_resolver import ResourceStateResolver


def loc(identifier, name):
    return SimpleNamespace(id=identifier, name=name, city=name, full_display=name)


def driver(identifier, name, *, model="2/1", rotation_start=date(2026, 7, 20)):
    first, last = name.split(" ", 1)
    return SimpleNamespace(
        id=identifier,
        first_name=first,
        last_name=last,
        full_name=name,
        active=True,
        absences=[],
        work_model=model,
        rotation_start=rotation_start,
        allowed_operation="Fernverkehr",
        home_base_location=None,
        home_base="Leipzig",
    )


def test_second_work_week_keeps_remote_vehicle_location_on_monday():
    base = loc(1, "Leipzig")
    remote = loc(2, "Wustermark")
    current_driver = driver(11, "Alt Fahrer", rotation_start=date(2026, 7, 20))
    current_driver.home_base_location = base
    vehicle = SimpleNamespace(
        operation_type="Fernverkehr",
        daily_return_required=False,
        home_base_location=base,
        home_base="Leipzig",
        staffing_profile=None,
    )
    last_tour = SimpleNamespace(
        driver_id=11,
        tour_date=date(2026, 7, 31),
        positions=[SimpleNamespace(transport_order=SimpleNamespace(unloading_location=remote))],
    )

    state = ResourceStateResolver().resolve(
        vehicle,
        current_driver,
        date(2026, 8, 3),
        datetime(2026, 8, 3, 5),
        last_tour,
    )

    assert state.start_location is remote


def test_new_driver_cycle_starts_vehicle_planning_at_base_on_monday():
    base = loc(1, "Leipzig")
    remote = loc(2, "Wustermark")
    new_driver = driver(12, "Neu Fahrer", rotation_start=date(2026, 8, 3))
    new_driver.home_base_location = base
    vehicle = SimpleNamespace(
        operation_type="Fernverkehr",
        daily_return_required=False,
        home_base_location=base,
        home_base="Leipzig",
        staffing_profile=None,
    )
    last_tour = SimpleNamespace(
        driver_id=11,
        tour_date=date(2026, 7, 31),
        positions=[SimpleNamespace(transport_order=SimpleNamespace(unloading_location=remote))],
    )

    state = ResourceStateResolver().resolve(
        vehicle,
        new_driver,
        date(2026, 8, 3),
        datetime(2026, 8, 3, 5),
        last_tour,
    )

    assert state.start_location is base
    assert "Heimatbasis" in state.reason


def test_work_minutes_are_separated_by_driver_shift():
    first = SimpleNamespace(vehicle_id=1510, driver_id=1, duty_start_at=datetime(2026, 7, 31, 5), shift_label="Schicht 1")
    second = SimpleNamespace(vehicle_id=1510, driver_id=2, duty_start_at=datetime(2026, 7, 31, 13, 30), shift_label="Schicht 2")

    assert AutomaticDispatcher._resource_work_key(first) != AutomaticDispatcher._resource_work_key(second)


def test_day_tour_creates_two_sequential_vehicle_resources():
    base = loc(1, "Leipzig")
    first_driver = driver(1, "Erster Fahrer")
    second_driver = driver(2, "Zweiter Fahrer")
    first_driver.home_base_location = base
    second_driver.home_base_location = base
    assignments = [
        SimpleNamespace(driver=first_driver, starts_at=datetime(2026, 7, 31, 5), ends_at=datetime(2026, 7, 31, 13, 30), sequence=1),
        SimpleNamespace(driver=second_driver, starts_at=datetime(2026, 7, 31, 13, 30), ends_at=datetime(2026, 7, 31, 22), sequence=2),
    ]
    tour = SimpleNamespace(
        id=99,
        vehicle_id=1510,
        tour_number="T-99",
        tour_date=date(2026, 7, 31),
        planned_start_time=time(5),
        driver_id=1,
        driver=first_driver,
        driver_display=first_driver.full_name,
        driver_assignments=assignments,
        positions=[],
        status="Geplant",
        trailer=None,
    )
    profile = SimpleNamespace(shift_minutes=510, sequential_double_shift=True, relief_driver_id=2)
    vehicle = SimpleNamespace(
        id=1510,
        license_plate="TS-ZM 1510",
        description="",
        active=True,
        operation_type="Nahverkehr",
        daily_return_required=True,
        home_base_location=base,
        home_base="Leipzig",
        staffing_profile=profile,
        trailer=None,
        vehicle_class="Standard",
        status="Aktiv",
        absences=[],
    )
    fake_schedule = SimpleNamespace(
        start_at=datetime(2026, 7, 31, 5),
        end_at=datetime(2026, 7, 31, 5),
    )
    engine = ResourceAvailabilityEngine(time_engine=SimpleNamespace(build_schedule=lambda _tour: fake_schedule))

    resources = engine.build([vehicle], [tour], date(2026, 7, 31))

    assert len(resources) == 2
    assert [resource.driver_id for resource in resources] == [1, 2]
    assert resources[0].duty_end_at == resources[1].duty_start_at
    assert resources[1].available_at == datetime(2026, 7, 31, 13, 30)
