from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ChainConnection:
    predecessor_id: int
    successor_id: int
    waiting_minutes: int
    downstream_potential: int


@dataclass(slots=True)
class TransportChainPlan:
    """Acyclic predecessor/successor graph for operational transport chains.

    Each order has at most one predecessor and one successor.  The detector may
    inspect several possible continuations, but commits the globally most useful
    links first.  This keeps a chain reservable for one vehicle while avoiding a
    merely local first-match decision.
    """

    predecessor_by_order: dict[int, int] = field(default_factory=dict)
    successor_by_order: dict[int, int] = field(default_factory=dict)
    connection_by_predecessor: dict[int, ChainConnection] = field(default_factory=dict)
    alternative_successors_by_order: dict[int, tuple[int, ...]] = field(default_factory=dict)

    def predecessor(self, order_id: int) -> int | None:
        return self.predecessor_by_order.get(int(order_id))

    def successor(self, order_id: int) -> int | None:
        return self.successor_by_order.get(int(order_id))

    def is_continuation(self, order_id: int) -> bool:
        return int(order_id) in self.predecessor_by_order

    def chain_length_from(self, order_id: int) -> int:
        return len(self.chain_ids_from(order_id))

    def chain_ids_from(self, order_id: int) -> list[int]:
        result = [int(order_id)]
        seen = set(result)
        while result[-1] in self.successor_by_order:
            successor = self.successor_by_order[result[-1]]
            if successor in seen:
                break
            result.append(successor)
            seen.add(successor)
        return result

    def roots(self) -> list[int]:
        connected = set(self.predecessor_by_order) | set(self.successor_by_order)
        return sorted(order_id for order_id in connected if order_id not in self.predecessor_by_order)

    def chains(self) -> list[list[int]]:
        result = [self.chain_ids_from(root) for root in self.roots()]
        covered = {order_id for chain in result for order_id in chain}
        for order_id in sorted((set(self.predecessor_by_order) | set(self.successor_by_order)) - covered):
            result.append(self.chain_ids_from(order_id))
            covered.update(result[-1])
        return result

    def connection(self, order_id: int) -> ChainConnection | None:
        return self.connection_by_predecessor.get(int(order_id))

    def alternative_successors(self, order_id: int) -> tuple[int, ...]:
        return self.alternative_successors_by_order.get(int(order_id), ())

    def chain_score_from(self, order_id: int, orders_by_id: dict[int, object]) -> int:
        """Internal planning value for a path, independent of a concrete vehicle."""
        chain = self.chain_ids_from(order_id)
        if len(chain) <= 1:
            return 0
        score = (len(chain) - 1) * 100
        waiting = sum(
            self.connection_by_predecessor[item].waiting_minutes
            for item in chain[:-1]
            if item in self.connection_by_predecessor
        )
        score -= min(120, waiting // 15)
        if self.is_round_trip(order_id, orders_by_id):
            score += 180
        return max(0, score)

    def is_round_trip(self, order_id: int, orders_by_id: dict[int, object]) -> bool:
        chain = self.chain_ids_from(order_id)
        if len(chain) < 2:
            return False
        first = orders_by_id.get(chain[0])
        last = orders_by_id.get(chain[-1])
        if first is None or last is None:
            return False
        return (
            TransportChainDetector._location_id(first, "loading")
            == TransportChainDetector._location_id(last, "unloading")
        )

    def round_trip_roots(self, orders_by_id: dict[int, object]) -> list[int]:
        return [root for root in self.roots() if self.is_round_trip(root, orders_by_id)]


class TransportChainDetector:
    """Builds a branch-aware, deterministic transport graph.

    All chronologically possible location matches are collected first.  Edges
    that unlock the longest downstream path are selected before shorter local
    matches.  Degree and cycle checks then produce safe linear vehicle chains.
    """

    def build(self, orders: Iterable[object]) -> TransportChainPlan:
        items = list(orders)
        plan = TransportChainPlan()
        if not items:
            return plan

        possible: dict[int, list[object]] = {}
        for predecessor in items:
            predecessor_id = int(predecessor.id)
            unloading_location_id = self._location_id(predecessor, "unloading")
            if unloading_location_id is None:
                continue
            successors = [
                successor
                for successor in items
                if int(successor.id) != predecessor_id
                and self._location_id(successor, "loading") == unloading_location_id
                and self._chronologically_connectable(predecessor, successor)
            ]
            successors.sort(key=lambda item: (self._loading_sort_key(item), int(item.id)))
            possible[predecessor_id] = successors
            plan.alternative_successors_by_order[predecessor_id] = tuple(int(item.id) for item in successors)

        memo: dict[int, int] = {}

        def downstream_depth(order_id: int, visiting: set[int] | None = None) -> int:
            if order_id in memo:
                return memo[order_id]
            visiting = set(visiting or ())
            if order_id in visiting:
                return 0
            visiting.add(order_id)
            depth = 0
            for successor in possible.get(order_id, []):
                successor_id = int(successor.id)
                depth = max(depth, 1 + downstream_depth(successor_id, visiting))
            memo[order_id] = depth
            return depth

        edges: list[tuple[tuple, object, object]] = []
        by_id = {int(item.id): item for item in items}
        for predecessor_id, successors in possible.items():
            predecessor = by_id[predecessor_id]
            for successor in successors:
                successor_id = int(successor.id)
                gap = self._waiting_minutes(predecessor, successor)
                potential = 1 + downstream_depth(successor_id)
                # Prefer a useful long continuation, then a tight transition,
                # then stable chronological and ID tie-breakers.
                rank = (
                    -potential,
                    gap,
                    self._loading_sort_key(successor),
                    predecessor_id,
                    successor_id,
                )
                edges.append((rank, predecessor, successor))

        for _, predecessor, successor in sorted(edges, key=lambda item: item[0]):
            predecessor_id = int(predecessor.id)
            successor_id = int(successor.id)
            if predecessor_id in plan.successor_by_order:
                continue
            if successor_id in plan.predecessor_by_order:
                continue
            if predecessor_id in plan.chain_ids_from(successor_id):
                continue
            connection = ChainConnection(
                predecessor_id=predecessor_id,
                successor_id=successor_id,
                waiting_minutes=self._waiting_minutes(predecessor, successor),
                downstream_potential=1 + downstream_depth(successor_id),
            )
            plan.successor_by_order[predecessor_id] = successor_id
            plan.predecessor_by_order[successor_id] = predecessor_id
            plan.connection_by_predecessor[predecessor_id] = connection

        return plan

    @staticmethod
    def _location_id(order: object, prefix: str) -> int | None:
        value = getattr(order, f"{prefix}_location_id", None)
        if value is None:
            location = getattr(order, f"{prefix}_location", None)
            value = getattr(location, "id", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _loading_sort_key(order: object) -> tuple:
        return (
            getattr(order, "loading_date", date.min),
            getattr(order, "loading_time_from", time.min) or time.min,
            int(getattr(order, "id", 0)),
        )

    @staticmethod
    def _event_datetime(order: object, prefix: str, *, end: bool) -> datetime | None:
        day = getattr(order, f"{prefix}_date", None)
        if day is None:
            return None
        if end:
            value = (
                getattr(order, f"{prefix}_time_until", None)
                or getattr(order, f"{prefix}_time_from", None)
                or time.max
            )
        else:
            value = (
                getattr(order, f"{prefix}_time_from", None)
                or getattr(order, f"{prefix}_time_until", None)
                or time.min
            )
        return datetime.combine(day, value)

    @classmethod
    def _waiting_minutes(cls, predecessor: object, successor: object) -> int:
        unload_time = (
            getattr(predecessor, "unloading_time_until", None)
            or getattr(predecessor, "unloading_time_from", None)
        )
        load_time = (
            getattr(successor, "loading_time_from", None)
            or getattr(successor, "loading_time_until", None)
        )
        if unload_time is None or load_time is None:
            return 0
        unload = datetime.combine(getattr(predecessor, "unloading_date"), unload_time)
        load = datetime.combine(getattr(successor, "loading_date"), load_time)
        return max(0, round((load - unload).total_seconds() / 60))

    @classmethod
    def _chronologically_connectable(cls, predecessor: object, successor: object) -> bool:
        unload_day = getattr(predecessor, "unloading_date", None)
        load_day = getattr(successor, "loading_date", None)
        if unload_day is None or load_day is None or unload_day > load_day:
            return False
        if unload_day < load_day:
            return True
        unload_time = (
            getattr(predecessor, "unloading_time_until", None)
            or getattr(predecessor, "unloading_time_from", None)
        )
        load_latest = (
            getattr(successor, "loading_time_until", None)
            or getattr(successor, "loading_time_from", None)
        )
        # Missing times represent an open operational window, as in the
        # established V3.1 semantics. Concrete feasibility remains in scoring.
        if unload_time is None or load_latest is None:
            return True
        return unload_time <= load_latest
