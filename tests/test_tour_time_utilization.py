from datetime import datetime
from types import SimpleNamespace

from leipzigerflow.ui.tour_utilization import calculate_tour_time_utilization


def test_working_time_is_primary_utilization_metric():
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=None))
    schedule = SimpleNamespace(
        duty_days=[SimpleNamespace(shift_minutes=8 * 60)],
        deployment_days=1,
        total_driving_minutes=5 * 60,
        start_at=datetime(2026, 7, 27, 6, 0),
        end_at=datetime(2026, 7, 27, 14, 0),
    )
    result = calculate_tour_time_utilization(tour, schedule)
    assert result.work_minutes == 480
    assert result.capacity_minutes == 600
    assert result.utilization_percent == 80.0
    assert result.status_text == "sehr gute Auslastung"


def test_legacy_nine_hour_profile_is_shown_with_ten_hour_capacity():
    profile = SimpleNamespace(shift_minutes=9 * 60, sequential_double_shift=False, relief_driver_id=None)
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=profile))
    schedule = SimpleNamespace(
        duty_days=[SimpleNamespace(shift_minutes=9 * 60)],
        deployment_days=1,
        total_driving_minutes=6 * 60,
        start_at=datetime(2026, 7, 27, 6, 0),
        end_at=datetime(2026, 7, 27, 15, 0),
    )
    result = calculate_tour_time_utilization(tour, schedule)
    assert result.capacity_minutes == 600
    assert result.work_text == "9:00 h / 10:00 h"
    assert result.utilization_percent == 90.0


def test_multiday_card_uses_peak_real_workday_and_single_day_capacity():
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=None))
    schedule = SimpleNamespace(
        duty_days=[
            SimpleNamespace(working_minutes=5 * 60 + 59, shift_minutes=8 * 60 + 59),
            SimpleNamespace(working_minutes=45, shift_minutes=45),
        ],
        deployment_days=3,
        total_driving_minutes=4 * 60,
        start_at=datetime(2026, 7, 25, 7, 0),
        end_at=datetime(2026, 7, 27, 7, 0),
    )
    result = calculate_tour_time_utilization(tour, schedule)
    assert result.work_minutes == 5 * 60 + 59
    assert result.capacity_minutes == 10 * 60
    assert result.work_text == "5:59 h / 10:00 h"
    assert round(result.utilization_percent) == 60
    assert result.deployment_days == 2


def test_calendar_waiting_days_do_not_increase_utilization_capacity():
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=None))
    schedule = SimpleNamespace(
        duty_days=[SimpleNamespace(working_minutes=8 * 60 + 59, shift_minutes=8 * 60 + 59)],
        deployment_days=2,
        total_driving_minutes=5 * 60,
        start_at=datetime(2026, 7, 24, 6, 0),
        end_at=datetime(2026, 7, 25, 7, 0),
    )
    result = calculate_tour_time_utilization(tour, schedule)
    assert result.work_text == "8:59 h / 10:00 h"
    assert round(result.utilization_percent) == 90
