from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from leipzigerflow.services.trailer_compatibility import parse_trailer_types


@dataclass(frozen=True, slots=True)
class FleetPlanningContext:
    """Snapshot of fleet supply and upcoming demand used by soft scoring rules."""

    free_by_trailer_type: dict[str, int] = field(default_factory=dict)
    demand_by_trailer_type: dict[str, int] = field(default_factory=dict)
    total_resources: int = 0
    total_orders: int = 0

    @classmethod
    def build(cls, resources, orders) -> "FleetPlanningContext":
        supply: Counter[str] = Counter()
        demand: Counter[str] = Counter()
        for resource in resources:
            trailer_type = str(getattr(resource, "trailer_type", "") or "").strip()
            if trailer_type:
                supply[trailer_type] += 1
        for order in orders:
            accepted = parse_trailer_types(getattr(order, "required_trailer_type", "Plane"))
            # Only compulsory requirements count fully. Flexible orders contribute
            # proportionally, avoiding artificial inflation of every allowed type.
            contribution = 1.0 / max(1, len(accepted))
            for trailer_type in accepted:
                demand[trailer_type] += contribution
        return cls(
            free_by_trailer_type=dict(supply),
            demand_by_trailer_type={key: round(value, 3) for key, value in demand.items()},
            total_resources=len(resources),
            total_orders=len(orders),
        )

    def scarcity(self, trailer_type: str) -> float:
        """Return 0..1 scarcity; 1 means demand exists but no free resource."""
        demand = float(self.demand_by_trailer_type.get(trailer_type, 0.0))
        supply = int(self.free_by_trailer_type.get(trailer_type, 0))
        if demand <= 0:
            return 0.0
        if supply <= 0:
            return 1.0
        return max(0.0, min(1.0, demand / supply))
