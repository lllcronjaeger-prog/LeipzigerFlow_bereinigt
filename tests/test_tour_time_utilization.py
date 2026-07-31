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


def test_single_driver_assignment_does_not_shorten_operational_work_time():
    assignment = SimpleNamespace(
        driver_id=7,
        starts_at=datetime(2026, 7, 31, 6, 0),
        ends_at=datetime(2026, 7, 31, 10, 0),
    )
    tour = SimpleNamespace(
        vehicle=SimpleNamespace(staffing_profile=None),
        driver_assignments=[assignment],
    )
    schedule = SimpleNamespace(
        duty_days=[SimpleNamespace(working_minutes=9 * 60, shift_minutes=9 * 60)],
        total_driving_minutes=6 * 60,
        start_at=datetime(2026, 7, 31, 6, 0),
        end_at=datetime(2026, 7, 31, 15, 0),
        travels=[],
        stops=[],
    )

    result = calculate_tour_time_utilization(tour, schedule)

    assert result.work_minutes == 9 * 60
    assert result.work_text == "9:00 h / 10:00 h"


def test_driver_change_counts_only_productive_overlap_not_daily_rest():
    assignments = [
        SimpleNamespace(
            driver_id=1,
            starts_at=datetime(2026, 7, 31, 6, 0),
            ends_at=datetime(2026, 7, 31, 16, 0),
        ),
        SimpleNamespace(
            driver_id=2,
            starts_at=datetime(2026, 7, 31, 16, 0),
            ends_at=datetime(2026, 8, 1, 9, 0),
        ),
    ]
    tour = SimpleNamespace(
        vehicle=SimpleNamespace(staffing_profile=None),
        driver_assignments=assignments,
    )
    schedule = SimpleNamespace(
        duty_days=[SimpleNamespace(working_minutes=8 * 60, shift_minutes=10 * 60)],
        total_driving_minutes=7 * 60,
        start_at=datetime(2026, 7, 31, 6, 0),
        end_at=datetime(2026, 8, 1, 9, 0),
        travels=[
            SimpleNamespace(
                started_at=datetime(2026, 7, 31, 6, 0),
                ended_at=datetime(2026, 7, 31, 14, 0),
            ),
            SimpleNamespace(
                started_at=datetime(2026, 8, 1, 6, 0),
                ended_at=datetime(2026, 8, 1, 9, 0),
            ),
        ],
        stops=[],
    )

    result = calculate_tour_time_utilization(tour, schedule)

    assert result.work_minutes == 8 * 60
    assert result.work_minutes != 17 * 60


def test_planning_date_counts_only_productive_work_of_that_calendar_day():
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=None), driver_assignments=[])
    schedule = SimpleNamespace(
        duty_days=[],
        total_driving_minutes=12 * 60,
        start_at=datetime(2026, 7, 31, 18, 0),
        end_at=datetime(2026, 8, 1, 8, 0),
        travels=[
            SimpleNamespace(started_at=datetime(2026, 7, 31, 18, 0), ended_at=datetime(2026, 7, 31, 22, 0)),
            SimpleNamespace(started_at=datetime(2026, 8, 1, 4, 0), ended_at=datetime(2026, 8, 1, 8, 0)),
        ],
        stops=[],
    )

    first_day = calculate_tour_time_utilization(tour, schedule, planning_date=datetime(2026, 7, 31).date())
    next_day = calculate_tour_time_utilization(tour, schedule, planning_date=datetime(2026, 8, 1).date())

    assert first_day.work_minutes == 4 * 60
    assert next_day.work_minutes == 4 * 60
    assert first_day.utilization_percent == 40.0
    assert next_day.utilization_percent == 40.0


def test_planning_date_splits_productive_interval_at_midnight():
    tour = SimpleNamespace(vehicle=SimpleNamespace(staffing_profile=None), driver_assignments=[])
    schedule = SimpleNamespace(
        duty_days=[],
        total_driving_minutes=120,
        start_at=datetime(2026, 7, 31, 23, 0),
        end_at=datetime(2026, 8, 1, 1, 0),
        travels=[SimpleNamespace(started_at=datetime(2026, 7, 31, 23, 0), ended_at=datetime(2026, 8, 1, 1, 0))],
        stops=[],
    )

    assert calculate_tour_time_utilization(tour, schedule, planning_date=datetime(2026, 7, 31).date()).work_minutes == 60
    assert calculate_tour_time_utilization(tour, schedule, planning_date=datetime(2026, 8, 1).date()).work_minutes == 60
