from __future__ import annotations

from datetime import datetime


def format_stop_period(
    label: str,
    arrival: datetime,
    departure: datetime,
    *,
    reference_date=None,
) -> str:
    """Formats a stop compactly while keeping multi-day dates visible.

    The date is omitted for same-day stops to keep tour cards compact. If the
    stop takes place on another calendar day than ``reference_date``, the date
    is placed directly before the time range.
    """
    date_prefix = ""
    if reference_date is not None and arrival.date() != reference_date:
        date_prefix = f"{arrival:%d.%m.} "
    return f"{label} <b>{date_prefix}{arrival:%H:%M}–{departure:%H:%M}</b>"


def format_tour_date_span(start_at: datetime, end_at: datetime) -> str:
    if start_at.date() == end_at.date():
        return f"{start_at:%d.%m.%Y}"
    if start_at.year == end_at.year and start_at.month == end_at.month:
        return f"{start_at:%d.}–{end_at:%d.%m.%Y}"
    if start_at.year == end_at.year:
        return f"{start_at:%d.%m.}–{end_at:%d.%m.%Y}"
    return f"{start_at:%d.%m.%Y}–{end_at:%d.%m.%Y}"
