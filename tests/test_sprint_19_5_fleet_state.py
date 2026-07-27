from datetime import date, datetime
from types import SimpleNamespace

from leipzigerflow.planner.engine.state_resolver import ResourceStateResolver


def loc(identifier, city):
    return SimpleNamespace(id=identifier, name=city, city=city, full_display=city)


def tour(day, destination):
    order = SimpleNamespace(unloading_location=destination)
    return SimpleNamespace(tour_date=day, positions=[SimpleNamespace(transport_order=order)])


def test_longhaul_keeps_mannheim_location_on_next_weekday():
    base = loc(1, "Ettlingen")
    mannheim = loc(2, "Mannheim")
    vehicle = SimpleNamespace(operation_type="Fernverkehr", daily_return_required=False, home_base_location=base, home_base="Ettlingen", staffing_profile=None)
    driver = SimpleNamespace(allowed_operation="Fernverkehr", work_model="MO-FR", home_base_location=base, home_base="Ettlingen")
    state = ResourceStateResolver().resolve(vehicle, driver, date(2026, 7, 28), datetime(2026, 7, 28, 6), tour(date(2026, 7, 27), mannheim))
    assert state.return_to_base_required is False
    assert state.start_location is mannheim


def test_longhaul_resets_to_base_on_monday():
    base = loc(1, "Ettlingen")
    mannheim = loc(2, "Mannheim")
    vehicle = SimpleNamespace(operation_type="Fernverkehr", daily_return_required=False, home_base_location=base, home_base="Ettlingen", staffing_profile=None)
    driver = SimpleNamespace(allowed_operation="Fernverkehr", work_model="MO-FR", home_base_location=base, home_base="Ettlingen")
    state = ResourceStateResolver().resolve(vehicle, driver, date(2026, 8, 3), datetime(2026, 8, 3, 6), tour(date(2026, 7, 31), mannheim))
    assert state.return_to_base_required is False
    assert state.start_location is base


def test_driver_home_base_has_priority_over_vehicle_home_base():
    driver_base = loc(1, "Ettlingen")
    vehicle_base = loc(2, "Leipzig")
    vehicle = SimpleNamespace(operation_type="Nahverkehr", daily_return_required=True, home_base_location=vehicle_base, home_base="Leipzig", staffing_profile=None)
    driver = SimpleNamespace(allowed_operation="Nahverkehr", work_model="MO-FR", home_base_location=driver_base, home_base="Ettlingen")
    state = ResourceStateResolver().resolve(vehicle, driver, date(2026, 7, 28), datetime(2026, 7, 28, 6))
    assert state.home_base_location is driver_base
    assert state.start_location is driver_base
