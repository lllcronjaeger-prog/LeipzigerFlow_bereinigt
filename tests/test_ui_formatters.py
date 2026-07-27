from datetime import datetime

from leipzigerflow.ui.formatters import format_stop_period, format_tour_date_span


def test_unloading_date_is_visible_on_following_day():
    loading_day = datetime(2026, 7, 23, 8, 0)
    arrival = datetime(2026, 7, 24, 7, 0)
    departure = datetime(2026, 7, 24, 8, 0)
    text = format_stop_period(
        "Entladen", arrival, departure, reference_date=loading_day.date()
    )
    assert "24.07." in text
    assert "07:00–08:00" in text


def test_same_day_stop_remains_compact():
    arrival = datetime(2026, 7, 23, 13, 30)
    departure = datetime(2026, 7, 23, 14, 0)
    text = format_stop_period(
        "Entladen", arrival, departure, reference_date=arrival.date()
    )
    assert "23.07." not in text
    assert "13:30–14:00" in text


def test_date_span_formats_multiday_tour():
    assert format_tour_date_span(
        datetime(2026, 7, 23, 6, 0), datetime(2026, 7, 24, 8, 0)
    ) == "23.–24.07.2026"
