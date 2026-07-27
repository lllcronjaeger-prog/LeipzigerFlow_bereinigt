from __future__ import annotations

from datetime import datetime, timedelta
from itertools import permutations

from leipzigerflow.planner.optimizer.multi_stop import (
    MultiStopOptimizationResult,
    MultiStopOrder,
    MultiStopPlan,
    MultiStopViolation,
    PlannedOrderStop,
)
from leipzigerflow.planner.optimizer.route_provider import ConservativeRouteProvider, RouteProvider


class MultiStopTourOptimizer:
    """Evaluates and optimizes complete order sequences for a tour.

    Sprint 16.2 evaluates both the loaded legs of each order and the empty
    transfer legs between consecutive orders. Time windows, waiting time,
    distance and route estimation are included in a deterministic score.
    """

    def __init__(
        self,
        route_provider: RouteProvider | None = None,
        *,
        exhaustive_limit: int = 8,
        alternative_limit: int = 3,
    ) -> None:
        self.route_provider = route_provider or ConservativeRouteProvider()
        self.exhaustive_limit = max(2, int(exhaustive_limit))
        self.alternative_limit = max(0, int(alternative_limit))

    def optimize(
        self,
        orders: list[MultiStopOrder] | tuple[MultiStopOrder, ...],
        *,
        tour_start: datetime,
        tour_start_location_id: int | None = None,
    ) -> MultiStopOptimizationResult:
        items = tuple(orders)
        current = self.evaluate(
            items,
            tour_start=tour_start,
            tour_start_location_id=tour_start_location_id,
        )
        if len(items) < 2:
            return MultiStopOptimizationResult(current=current, optimized=current)

        plans = [
            self.evaluate(
                sequence,
                tour_start=tour_start,
                tour_start_location_id=tour_start_location_id,
            )
            for sequence in self._candidate_sequences(items)
        ]
        plans.sort(key=self._sort_key, reverse=True)
        optimized = plans[0]
        alternatives = tuple(
            plan for plan in plans[1:] if plan.order_ids != optimized.order_ids
        )[: self.alternative_limit]
        return MultiStopOptimizationResult(
            current=current,
            optimized=optimized,
            alternatives=alternatives,
        )

    def evaluate(
        self,
        orders: list[MultiStopOrder] | tuple[MultiStopOrder, ...],
        *,
        tour_start: datetime,
        tour_start_location_id: int | None = None,
    ) -> MultiStopPlan:
        cursor = tour_start
        previous_unloading_location: int | None = tour_start_location_id
        stops: list[PlannedOrderStop] = []
        violations: list[MultiStopViolation] = []
        explanations: list[str] = []

        transfer_minutes_total = 0
        loaded_drive_minutes_total = 0
        waiting_total = 0
        lateness_total = 0
        loaded_distance_total = 0.0
        empty_distance_total = 0.0
        distance_complete = True
        estimated_legs = 0

        initial_transfer_minutes = 0
        initial_transfer_distance: float | None = 0.0

        for sequence, order in enumerate(orders, start=1):
            transfer_minutes = 0
            transfer_distance: float | None = 0.0
            transfer_estimated = False

            if previous_unloading_location is not None:
                transfer_leg = self.route_provider.route(
                    previous_unloading_location,
                    order.loading_location_id,
                )
                transfer_minutes = int(transfer_leg.duration_minutes)
                transfer_distance = transfer_leg.distance_km
                transfer_estimated = bool(transfer_leg.estimated)
                cursor += timedelta(minutes=transfer_minutes)
                transfer_minutes_total += transfer_minutes
                if transfer_distance is None:
                    distance_complete = False
                else:
                    empty_distance_total += float(transfer_distance)
                if transfer_estimated:
                    estimated_legs += 1
                if sequence == 1 and tour_start_location_id is not None:
                    initial_transfer_minutes = transfer_minutes
                    initial_transfer_distance = transfer_distance

            loading_at = max(cursor, order.loading_window_start)
            waiting = max(0, int((loading_at - cursor).total_seconds() // 60))
            waiting_total += waiting
            if loading_at > order.loading_window_end:
                lateness_total += max(
                    1, int((loading_at - order.loading_window_end).total_seconds() // 60)
                )
                violations.append(
                    MultiStopViolation(
                        order.order_id,
                        order.order_number,
                        "Ladezeitfenster wird überschritten.",
                    )
                )

            after_loading = loading_at + timedelta(minutes=order.loading_duration_minutes)
            loaded_leg = self.route_provider.route(
                order.loading_location_id,
                order.unloading_location_id,
            )
            loaded_drive_minutes = int(loaded_leg.duration_minutes)
            loaded_distance = loaded_leg.distance_km
            loaded_drive_minutes_total += loaded_drive_minutes
            if loaded_distance is None:
                distance_complete = False
            else:
                loaded_distance_total += float(loaded_distance)
            if loaded_leg.estimated:
                estimated_legs += 1

            unloading_arrival = after_loading + timedelta(minutes=loaded_drive_minutes)
            unloading_at = max(unloading_arrival, order.unloading_window_start)
            unloading_waiting = max(
                0, int((unloading_at - unloading_arrival).total_seconds() // 60)
            )
            waiting += unloading_waiting
            waiting_total += unloading_waiting

            if unloading_at > order.unloading_window_end:
                lateness_total += max(
                    1, int((unloading_at - order.unloading_window_end).total_seconds() // 60)
                )
                violations.append(
                    MultiStopViolation(
                        order.order_id,
                        order.order_number,
                        "Entladezeitfenster wird überschritten.",
                    )
                )

            cursor = unloading_at + timedelta(minutes=order.unloading_duration_minutes)
            previous_unloading_location = order.unloading_location_id
            stops.append(
                PlannedOrderStop(
                    order_id=order.order_id,
                    order_number=order.order_number,
                    sequence=sequence,
                    planned_loading_at=loading_at,
                    planned_unloading_at=unloading_at,
                    waiting_minutes=waiting,
                    transfer_minutes=transfer_minutes,
                    transfer_distance_km=transfer_distance,
                    loaded_drive_minutes=loaded_drive_minutes,
                    loaded_distance_km=loaded_distance,
                    estimated_route=transfer_estimated or bool(loaded_leg.estimated),
                )
            )

        total_drive_minutes = loaded_drive_minutes_total + transfer_minutes_total
        total_distance = (
            loaded_distance_total + empty_distance_total if distance_complete else None
        )

        continuity_matches = sum(
            1
            for previous, following in zip(orders, orders[1:])
            if previous.unloading_location_id == following.loading_location_id
        )

        score = 100
        score -= min(60, len(violations) * 30)
        score -= min(30, (lateness_total // 15) * 3)
        score -= min(20, (waiting_total // 30) * 2)
        score -= min(20, (transfer_minutes_total // 30) * 2)
        score -= min(10, estimated_legs)
        if total_distance and empty_distance_total:
            empty_share = empty_distance_total / total_distance
            score -= min(15, round(empty_share * 25))
        score += min(10, continuity_matches * 5)
        score = max(0, min(100, int(score)))

        if violations:
            label = "kritisch"
        elif score >= 85:
            label = "sehr gut"
        elif score >= 70:
            label = "gut"
        elif score >= 50:
            label = "verbesserbar"
        else:
            label = "ungünstig"

        if total_distance is not None:
            explanations.append(f"Gesamtstrecke: {total_distance:.1f} km.")
            explanations.append(f"Davon Leerfahrt: {empty_distance_total:.1f} km.")
        explanations.append(f"Fahrzeit insgesamt: {total_drive_minutes} Minuten.")
        if continuity_matches:
            explanations.append(
                f"{continuity_matches} direkter Standortübergang ohne Leerfahrt."
            )
        if waiting_total:
            explanations.append(f"Geplante Wartezeit insgesamt: {waiting_total} Minuten.")
        if tour_start_location_id is not None:
            if initial_transfer_distance is not None:
                explanations.append(
                    "Anfahrt vom Fahrzeugstandort zum ersten Auftrag: "
                    f"{initial_transfer_distance:.1f} km / {initial_transfer_minutes} Minuten."
                )
            else:
                explanations.append(
                    "Anfahrt vom Fahrzeugstandort zum ersten Auftrag wurde geschätzt."
                )
        if transfer_minutes_total:
            explanations.append(
                f"Leerfahrt einschließlich Startanfahrt: {transfer_minutes_total} Minuten."
            )
        if estimated_legs:
            explanations.append(
                f"{estimated_legs} Streckenabschnitt(e) wurden konservativ geschätzt."
            )
        if violations:
            explanations.append(
                f"{len(violations)} Zeitfensterverletzung(en), "
                f"insgesamt {lateness_total} Minuten Verspätung."
            )

        return MultiStopPlan(
            order_ids=tuple(order.order_id for order in orders),
            stops=tuple(stops),
            feasible=not violations,
            quality_score=score,
            quality_label=label,
            total_transfer_minutes=transfer_minutes_total,
            total_drive_minutes=total_drive_minutes,
            total_distance_km=total_distance,
            loaded_distance_km=loaded_distance_total if distance_complete else None,
            empty_distance_km=empty_distance_total if distance_complete else None,
            total_waiting_minutes=waiting_total,
            total_lateness_minutes=lateness_total,
            estimated_route_legs=estimated_legs,
            violations=tuple(violations),
            explanations=tuple(explanations),
        )

    def _candidate_sequences(
        self, orders: tuple[MultiStopOrder, ...]
    ) -> list[tuple[MultiStopOrder, ...]]:
        if len(orders) <= self.exhaustive_limit:
            return list(permutations(orders))

        sequences: list[tuple[MultiStopOrder, ...]] = [orders]
        for seed in orders[: min(8, len(orders))]:
            path = [seed]
            pool = [item for item in orders if item is not seed]
            while pool:
                previous = path[-1]
                pool.sort(
                    key=lambda item: (
                        self.route_provider.route(
                            previous.unloading_location_id,
                            item.loading_location_id,
                        ).duration_minutes,
                        item.loading_window_end,
                        item.unloading_window_end,
                        item.order_number,
                    )
                )
                path.append(pool.pop(0))
            sequences.append(tuple(path))

        unique: dict[tuple[int, ...], tuple[MultiStopOrder, ...]] = {}
        for sequence in sequences:
            unique[tuple(item.order_id for item in sequence)] = sequence
        return list(unique.values())

    @staticmethod
    def _sort_key(plan: MultiStopPlan) -> tuple:
        distance = plan.total_distance_km if plan.total_distance_km is not None else float("inf")
        return (
            1 if plan.feasible else 0,
            -len(plan.violations),
            -plan.total_lateness_minutes,
            plan.quality_score,
            -plan.total_waiting_minutes,
            -plan.total_transfer_minutes,
            -distance,
            -plan.total_drive_minutes,
            tuple(-value for value in plan.order_ids),
        )
