from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    started_at: datetime
    ended_at: datetime
    kind: str
    title: str
    detail: str = ""


def build_timeline_entries(schedule) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    for stop in schedule.stops:
        kind = "loading" if stop.kind == "Laden" else "unloading"
        entries.append(TimelineEntry(
            stop.planned_arrival, stop.planned_departure, kind,
            f"{stop.kind} · {stop.location_name}", stop.order_number,
        ))
    for travel in schedule.travels:
        kind = "empty_run" if getattr(travel, "is_empty_run", False) else "loaded_travel"
        distance = f"{travel.distance_km:.1f} km" if travel.distance_km is not None else "Entfernung geschätzt"
        entries.append(TimelineEntry(
            travel.started_at, travel.ended_at, kind,
            f"{travel.origin_name} → {travel.destination_name}", distance,
        ))
    for item in schedule.breaks:
        kind = "rest" if getattr(item, "is_daily_rest", False) else (
            "waiting" if "Warte" in item.reason else "break"
        )
        entries.append(TimelineEntry(item.started_at, item.ended_at, kind, item.reason, f"{item.minutes} Min."))
    return sorted(entries, key=lambda item: (item.started_at, item.ended_at, item.kind))
