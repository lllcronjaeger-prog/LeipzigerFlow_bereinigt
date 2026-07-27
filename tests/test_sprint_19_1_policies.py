from datetime import date
from types import SimpleNamespace

from leipzigerflow.services.disposition_policy import DispositionPolicy
from leipzigerflow.services.rotation_manager import RotationManager
from leipzigerflow.services.working_time_manager import WorkingTimeManager


def test_two_one_rotation_is_automatic_and_absence_overlays_cycle():
    driver=SimpleNamespace(active=True, work_model="2/1", rotation_start=date(2026,8,3), absence_from=None, absence_until=None, absence_reason="")
    manager=RotationManager()
    assert manager.status(driver,date(2026,8,3)).available
    assert manager.status(driver,date(2026,8,16)).available
    assert not manager.status(driver,date(2026,8,17)).available
    driver.absence_from=date(2026,8,5); driver.absence_until=date(2026,8,7); driver.absence_reason="Urlaub"
    assert manager.status(driver,date(2026,8,6)).phase == "Urlaub"
    assert manager.status(driver,date(2026,8,10)).available


def test_three_one_rotation_has_three_work_weeks_and_one_free_week():
    d=SimpleNamespace(active=True,work_model="3/1",rotation_start=date(2026,8,3),absence_from=None,absence_until=None)
    m=RotationManager()
    assert m.status(d,date(2026,8,23)).available
    assert not m.status(d,date(2026,8,24)).available


def test_working_time_checks_break_day_week_and_double_week():
    d=SimpleNamespace(weekly_target_minutes=2880,double_week_limit_minutes=5760)
    day=date(2026,8,10)
    history={day:500}
    result=WorkingTimeManager().evaluate(d,day,history,80)
    assert result.required_break_minutes == 45
    assert not result.feasible
    assert "Tägliche Arbeitszeit" in result.reasons[0]


def test_local_vehicle_must_return_to_ettlingen():
    vehicle=SimpleNamespace(operation_type="Nahverkehr",home_base="Ettlingen",overnight_away_allowed=False)
    driver=SimpleNamespace(allowed_operation="Beides")
    policy=DispositionPolicy()
    assert policy.evaluate_end_of_day(vehicle,driver,"Ettlingen",False).feasible
    result=policy.evaluate_end_of_day(vehicle,driver,"Mannheim",False)
    assert not result.feasible
    assert "Basis Ettlingen" in result.reasons[0]


def test_long_haul_vehicle_can_rest_away():
    vehicle=SimpleNamespace(operation_type="Fernverkehr",home_base="Ettlingen",overnight_away_allowed=True)
    driver=SimpleNamespace(allowed_operation="Fernverkehr")
    assert DispositionPolicy().evaluate_end_of_day(vehicle,driver,"Koblenz",True).feasible
