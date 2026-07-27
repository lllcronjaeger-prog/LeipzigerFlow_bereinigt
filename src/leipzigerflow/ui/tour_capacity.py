from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Any


@dataclass(frozen=True, slots=True)
class PeakTourLoad:
    weight_kg: Decimal = Decimal("0")
    loading_meters: Decimal = Decimal("0")
    pallets: int = 0

    @property
    def utilization_percent(self) -> float:
        percentages = (
            float(self.weight_kg / Decimal("24000") * 100) if self.weight_kg else 0.0,
            float(self.loading_meters / Decimal("13.6") * 100) if self.loading_meters else 0.0,
            float(Decimal(self.pallets) / Decimal("34") * 100) if self.pallets else 0.0,
        )
        return max(percentages)


def calculate_peak_tour_load(positions: Iterable[Any], stops: Iterable[Any]) -> PeakTourLoad:
    """Return the highest simultaneous load during a tour.

    Multiple sequential full-load orders must not be added together. Loads are
    added after a loading stop and removed at an unloading stop. If no usable
    schedule is available, the largest single order is used as a safe fallback.
    """
    loads: dict[int, PeakTourLoad] = {}
    for position in positions:
        order = getattr(position, "transport_order", None)
        order_id = getattr(order, "id", None)
        if order is None or order_id is None:
            continue
        loads[int(order_id)] = PeakTourLoad(
            weight_kg=Decimal(str(getattr(order, "weight_kg", 0) or 0)),
            loading_meters=Decimal(str(getattr(order, "loading_meters", 0) or 0)),
            pallets=int(getattr(order, "pallets", 0) or 0),
        )

    if not loads:
        return PeakTourLoad()

    # At an identical timestamp, unloading comes before loading. This prevents
    # a false temporary overload when a follow-up load starts at the same place.
    event_rows: list[tuple[Any, int, int, str]] = []
    for stop in stops:
        order_id = getattr(stop, "order_id", None)
        kind = str(getattr(stop, "kind", ""))
        if order_id is None or int(order_id) not in loads or kind not in {"Laden", "Entladen"}:
            continue
        timestamp = (
            getattr(stop, "planned_departure", None)
            if kind == "Laden"
            else getattr(stop, "planned_arrival", None)
        )
        if timestamp is None:
            continue
        event_rows.append((timestamp, 0 if kind == "Entladen" else 1, int(order_id), kind))

    if not event_rows:
        return max(loads.values(), key=lambda load: load.utilization_percent)

    current_weight = Decimal("0")
    current_loading_meters = Decimal("0")
    current_pallets = 0
    peak = PeakTourLoad()
    loaded_orders: set[int] = set()

    for _timestamp, _sort_order, order_id, kind in sorted(event_rows):
        load = loads[order_id]
        if kind == "Entladen":
            if order_id not in loaded_orders:
                continue
            current_weight = max(Decimal("0"), current_weight - load.weight_kg)
            current_loading_meters = max(Decimal("0"), current_loading_meters - load.loading_meters)
            current_pallets = max(0, current_pallets - load.pallets)
            loaded_orders.discard(order_id)
            continue

        if order_id in loaded_orders:
            continue
        current_weight += load.weight_kg
        current_loading_meters += load.loading_meters
        current_pallets += load.pallets
        loaded_orders.add(order_id)

        candidate = PeakTourLoad(current_weight, current_loading_meters, current_pallets)
        if candidate.utilization_percent > peak.utilization_percent:
            peak = candidate

    return peak
