from __future__ import annotations

from copy import replace
from datetime import date, datetime, timedelta
from time import perf_counter

from leipzigerflow.planner.engine.context import FleetPlanningContext
from leipzigerflow.planner.engine.decision_log import CandidateDecision
from leipzigerflow.planner.engine.history import DecisionHistoryEntry, DecisionHistoryStore
from leipzigerflow.planner.engine.models import (
    AlternativeAssignment,
    DispatchSimulationResult,
    DispatchWeights,
    ProposedAssignment,
    PlanningSuggestion,
    PlanningPhase,
    PlanningStrategy,
    ResourceState,
    UnassignedOrder,
    VehicleCapacity,
)
from leipzigerflow.planner.engine.optimizer import DispatchOptimizer, OptimizationProfile
from leipzigerflow.planner.engine.planning_core import PlanningEngineCore
from leipzigerflow.planner.engine.priority import OrderPriorityEngine
from leipzigerflow.planner.engine.rules import DispatchRules
from leipzigerflow.planner.engine.scoring import AssignmentScoringEngine
from leipzigerflow.planner.engine.tour_builder import AutomaticTourBuilder
from leipzigerflow.planner.engine.transport_chains import TransportChainDetector
from leipzigerflow.planner.engine.workday import WorkdayCalculator
from leipzigerflow.planner.engine.multiday import FutureDemandIndex
from leipzigerflow.routing import get_default_routing_service


class AutomaticDispatcher:
    """Deterministische, ressourcenorientierte Disposition mit Transparenz."""

    MAX_ALTERNATIVES = 3

    def __init__(
        self,
        weights: DispatchWeights | None = None,
        rules: DispatchRules | None = None,
        history_store: DecisionHistoryStore | None = None,
        routing_service=None,
    ):
        self.weights = weights or DispatchWeights()
        self.rules = rules or DispatchRules()
        self.rules.validate()
        self.priority_engine = OrderPriorityEngine()
        self.scoring_engine = AssignmentScoringEngine(weights=self.weights, rules=self.rules)
        self.optimizer = DispatchOptimizer(self.rules)
        self.history_store = history_store
        self.tour_builder = AutomaticTourBuilder()
        self.chain_detector = TransportChainDetector()
        self.planning_core = PlanningEngineCore()
        self.routing_service = routing_service or get_default_routing_service()
        self.workday_calculator = WorkdayCalculator(
            fallback_route_minutes=int(getattr(self.scoring_engine, "TRANSFER_MINUTES", 30) or 30)
        )

    def simulate(
        self,
        resources,
        orders,
        planning_day: date,
        profile: OptimizationProfile = OptimizationProfile.BALANCED,
        replanning_reasons: list[str] | None = None,
        strategy: PlanningStrategy = PlanningStrategy.MAX_UTILIZATION,
        future_orders_by_day: dict[date, list] | None = None,
    ) -> DispatchSimulationResult:
        started = perf_counter()
        result = DispatchSimulationResult(
            created_at=datetime.now(),
            resources_total=len(resources),
            orders_total=len(orders),
            optimization_profile=profile.value,
            replanning_reasons=list(replanning_reasons or []),
            planning_strategy=strategy,
        )
        analysis = self.planning_core.analyse(resources, orders, planning_day)
        result.estimated_capacity_minutes = analysis.capacity_minutes
        result.estimated_demand_minutes = analysis.estimated_demand_minutes
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.DAY_ANALYSIS,
            f"{analysis.order_count} Aufträge und {analysis.unique_vehicle_count} Fahrzeuge erkannt",
            f"{analysis.driver_count} Fahrer und {analysis.resource_count} nutzbare Ressourcenschichten",
            1,
        ))
        balance = analysis.capacity_minutes - analysis.estimated_demand_minutes
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.CAPACITY_ANALYSIS,
            f"Tageskapazität {analysis.capacity_minutes // 60}:{analysis.capacity_minutes % 60:02d} h",
            (f"Geschätzter Bedarf {analysis.estimated_demand_minutes // 60}:{analysis.estimated_demand_minutes % 60:02d} h; "
             f"Reserve {max(0, balance) // 60}:{max(0, balance) % 60:02d} h" if balance >= 0 else
             f"Geschätzter Bedarf {analysis.estimated_demand_minutes // 60}:{analysis.estimated_demand_minutes % 60:02d} h; "
             f"Fehlkapazität {abs(balance) // 60}:{abs(balance) % 60:02d} h"),
            2,
        ))
        future_demand = FutureDemandIndex(future_orders_by_day or {})
        candidates = {int(order.id): self.priority_engine.build(order, planning_day) for order in orders}
        orders_by_id = {int(order.id): order for order in orders}
        route_by_order = {order_id: self._route_for_order(order) for order_id, order in orders_by_id.items()}
        remaining = set(orders_by_id)
        chain_plan = self.chain_detector.build(orders)
        chain_owner_by_order: dict[int, int] = {}
        chain_count = sum(
            1 for order_id in orders_by_id
            if chain_plan.chain_length_from(order_id) > 1
            and chain_plan.predecessor(order_id) is None
        )
        if chain_count:
            round_trip_count = len(chain_plan.round_trip_roots(orders_by_id))
            result.planning_trace.append(self.planning_core.trace(
                PlanningPhase.INITIAL_WAVE,
                f"{chain_count} zusammenhängende Transportkette(n) erkannt",
                "Folgeaufträge werden möglichst vollständig auf demselben Fahrzeug gehalten; "
                "Fremdvergabe wird erst nach Prüfung der Gesamtkette erwogen. "
                f"{round_trip_count} wirtschaftliche Rundtour(en) erkannt.",
                3,
            ))
        working_resources = list(resources)
        planning_context = FleetPlanningContext.build(resources, orders)
        assignments_by_vehicle: dict[int, int] = {}
        planned_minutes_by_vehicle: dict[int, int] = {}
        transfer_route_cache: dict[tuple[int | None, int | None], object | None] = {}
        transfer_cache_hits = 0
        transfer_cache_misses = 0
        candidate_evaluations = 0
        unique_vehicle_ids = {int(resource.vehicle_id) for resource in working_resources}
        unused_vehicle_ids = set(unique_vehicle_ids)
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.INITIAL_WAVE,
            "Parallele Erststarts werden vorbereitet",
            "Jedes verfügbare Fahrzeug erhält vor einer Wiederverwendung zunächst höchstens einen passenden Auftrag.",
            3,
        ))

        while remaining and working_resources:
            all_scores = []
            scores_by_order: dict[int, list] = {order_id: [] for order_id in remaining}

            for index, resource in enumerate(working_resources):
                for order_id in remaining:
                    predecessor_id = chain_plan.predecessor(order_id)
                    # Folgeaufträge dürfen erst nach ihrem Zubringer eingeplant
                    # werden. Nach dessen Zuweisung bleibt die Kette auf demselben
                    # Fahrzeug reserviert.
                    if predecessor_id is not None and predecessor_id in remaining:
                        continue
                    owner_vehicle_id = chain_owner_by_order.get(order_id)
                    if owner_vehicle_id is not None and int(resource.vehicle_id) != owner_vehicle_id:
                        continue
                    order = orders_by_id[order_id]
                    transfer_key = (
                        getattr(resource, "location_id", None),
                        getattr(order, "loading_location_id", None),
                    )
                    if transfer_key not in transfer_route_cache:
                        transfer_cache_misses += 1
                        transfer_route_cache[transfer_key] = self._transfer_route_for(resource, order)
                    else:
                        transfer_cache_hits += 1
                    transfer_route_result = transfer_route_cache[transfer_key]
                    candidate_evaluations += 1
                    score = self.scoring_engine.evaluate(
                        resource,
                        order,
                        candidates[order_id],
                        planning_context,
                        route_result=route_by_order.get(order_id),
                        transfer_route_result=transfer_route_result,
                    )
                    self._apply_hard_business_rules(
                        score,
                        order,
                        route_by_order.get(order_id),
                        resource=resource,
                        already_planned_minutes=planned_minutes_by_vehicle.get(resource.vehicle_id, 0),
                    )
                    prior_assignments = assignments_by_vehicle.get(resource.vehicle_id, 0)
                    if score.feasible:
                        self._apply_fleet_strategy_score(
                            score,
                            order,
                            route_by_order.get(order_id),
                        )
                        self._apply_state_transition_score(
                            score, order, resource=resource,
                            prior_assignments=prior_assignments,
                        )
                        planned_minutes = planned_minutes_by_vehicle.get(resource.vehicle_id, 0)
                        chain_length = chain_plan.chain_length_from(order_id)
                        is_reserved_continuation = owner_vehicle_id is not None
                        if is_reserved_continuation:
                            chain_bonus = 1000
                            score.score += chain_bonus
                            score.reasons.append(
                                f"Zusammenhängende Transportkette auf demselben Fahrzeug fortsetzen +{chain_bonus}"
                            )
                        elif chain_length > 1:
                            chain_value = chain_plan.chain_score_from(order_id, orders_by_id)
                            chain_bonus = 220 * (chain_length - 1) + min(240, chain_value // 2)
                            score.score += chain_bonus
                            score.reasons.append(
                                f"Global bewerteter Start einer Transportkette mit {chain_length} Aufträgen +{chain_bonus}"
                            )
                            if chain_plan.is_round_trip(order_id, orders_by_id):
                                round_trip_bonus = 180
                                score.score += round_trip_bonus
                                score.reasons.append(f"Rückladung schließt wirtschaftliche Rundtour +{round_trip_bonus}")
                        if strategy in {PlanningStrategy.MIN_EMPTY_RUN, PlanningStrategy.MIN_DISTANCE}:
                            empty_penalty = min(180, max(0, score.transfer_minutes) * 2)
                            score.score -= empty_penalty
                            if empty_penalty:
                                score.reasons.append(f"Strategie minimiert Leeranfahrt -{empty_penalty}")
                        elif strategy in {PlanningStrategy.OWN_FLEET_FIRST, PlanningStrategy.AVOID_SUBCONTRACTORS}:
                            own_fleet_bonus = 90
                            score.score += own_fleet_bonus
                            score.reasons.append(f"Eigenfuhrpark vor Fremdvergabe +{own_fleet_bonus}")
                        if prior_assignments and not is_reserved_continuation:
                            # Balance by occupied time, not just order count. This prevents one
                            # vehicle from absorbing the whole day while still allowing useful
                            # chains on an already started tour.
                            balance_penalty = min(90, 18 * prior_assignments + planned_minutes // 60 * 6)
                            score.score -= balance_penalty
                            score.reasons.append(
                                f"Flottenauslastung ausgleichen ({planned_minutes} bereits geplante Minuten) -{balance_penalty}"
                            )
                        elif assignments_by_vehicle and len(assignments_by_vehicle) < len({r.vehicle_id for r in working_resources}):
                            score.score += 12
                            score.reasons.append("Noch ungenutztes geeignetes Fahrzeug einbeziehen +12")
                        # Look-ahead is deliberately a soft rule. Local vehicles return
                        # to base and therefore receive no destination-positioning bonus.
                        if not getattr(resource, "return_to_base_required", False):
                            future_bonus, future_reasons = future_demand.score_for_destination(
                                getattr(order, "unloading_location_id", None), planning_day
                            )
                            if future_bonus:
                                score.score += future_bonus
                                score.reasons.extend(future_reasons)
                    result.candidate_decisions.append(
                        CandidateDecision.from_score(score, str(order.order_number))
                    )
                    scores_by_order[order_id].append(score)
                    if score.feasible:
                        all_scores.append((score, order, index))

            # Non-greedy initial wave: as long as unused vehicles have feasible
            # assignments, already used vehicles are excluded. This guarantees
            # parallel starts at the common opening time instead of artificial
            # 08:00/11:00 staggering caused by tour-extension bonuses.
            # Fachliche Priorität ist eine harte Auswahlstufe: Solange ein
            # Auftrag "Eigenfuhrpark bevorzugt" machbar ist, darf ein
            # Verkaufsauftrag keine eigene Ressource belegen. Erst innerhalb
            # derselben Prioritätsstufe entscheiden Ketten, Auslastung und Score.
            priority_scores = self._highest_dispatch_priority_scores(all_scores)
            reserved_chain_scores = [
                item for item in priority_scores
                if chain_owner_by_order.get(int(item[1].id)) == int(item[0].resource.vehicle_id)
            ]
            initial_wave_scores = [
                item for item in priority_scores if int(item[0].resource.vehicle_id) in unused_vehicle_ids
            ]
            # Eine bereits begonnene Kette wird nur innerhalb derselben
            # Dispositionspriorität fortgesetzt.
            considered_scores = reserved_chain_scores or initial_wave_scores or priority_scores
            ranked = self.optimizer.rank([item[0] for item in considered_scores], profile)
            if not ranked:
                self._append_unassigned(result, remaining, candidates, scores_by_order)
                break

            best_ranked = ranked[0]
            best = best_ranked.score
            matching = next(
                item for item in considered_scores
                if item[0] is best
            )
            best_order, resource_index = matching[1], matching[2]
            resource = working_resources[resource_index]
            evaluated_for_order = scores_by_order[int(best_order.id)]

            is_shuttle = str(getattr(best_order, "order_type", "") or "").strip().lower() == "shuttle"
            # Shuttles are repetitive and often have several nearly equivalent vehicle
            # choices. A low confidence value therefore reflects ambiguity, not a bad
            # or illegal assignment. Keep a feasible shuttle in the own fleet and use
            # the remaining duty capacity instead of leaving it artificially open.
            if best_ranked.confidence_percent < self.rules.minimum_confidence_percent and not is_shuttle:
                result.unassigned.append(
                    UnassignedOrder(
                        order_id=int(best_order.id),
                        order_number=str(best_order.order_number),
                        priority_score=candidates[int(best_order.id)].priority_score,
                        reasons=[
                            f"Vertrauensgrad {best_ranked.confidence_percent}% liegt unter "
                            f"Mindestwert {self.rules.minimum_confidence_percent}%"
                        ],
                        alternatives=self._alternatives(evaluated_for_order),
                    )
                )
                remaining.remove(int(best_order.id))
                continue

            alternatives = [
                alternative
                for alternative in self._alternatives(evaluated_for_order)
                if alternative.vehicle_label != resource.vehicle_label
            ][: self.MAX_ALTERNATIVES]
            route_result = route_by_order[int(best_order.id)]
            transfer_key = (
                getattr(resource, "location_id", None),
                getattr(best_order, "loading_location_id", None),
            )
            transfer_route = transfer_route_cache.get(transfer_key)
            if transfer_key not in transfer_route_cache:
                transfer_route = self._transfer_route_for(resource, best_order)
                transfer_route_cache[transfer_key] = transfer_route
            return_route = self._route_between(
                getattr(best_order, "unloading_location_id", None),
                getattr(resource, "home_base_location_id", None),
            ) if getattr(resource, "return_to_base_required", False) else None
            for decision in reversed(result.candidate_decisions):
                if (
                    decision.order_number == str(best_order.order_number)
                    and decision.vehicle_label == str(resource.vehicle_label)
                ):
                    decision.selected = True
                    break
            assignment = ProposedAssignment(
                vehicle_id=resource.vehicle_id,
                vehicle_label=resource.vehicle_label,
                driver_id=resource.driver_id,
                driver_label=resource.driver_label,
                order_id=int(best_order.id),
                order_number=best_order.order_number,
                score=best.score,
                loading_at=best.planned_loading_at,
                available_again_at=best.planned_available_at,
                mode=best.mode,
                source_tour_id=(resource.source_tour_id if resource.source_tour_id is not None else -resource.vehicle_id),
                source_tour_number=(resource.source_tour_number or "Neue Tour (Simulation)"),
                transfer_minutes=best.transfer_minutes,
                waiting_minutes=best.waiting_minutes,
                reasons=best.reasons,
                alternatives=alternatives,
                confidence_percent=best_ranked.confidence_percent,
                confidence_label=best_ranked.confidence_label,
                loading_location_label=getattr(best_order.loading_location, "full_display", ""),
                unloading_location_label=getattr(best_order.unloading_location, "full_display", ""),
                loading_date=best_order.loading_date,
                unloading_date=best_order.unloading_date,
                required_trailer_types=str(best_order.required_trailer_type or ""),
                unloading_at=best.planned_unloading_at,
                loading_rebooking_required=best.loading_rebooking_required,
                unloading_rebooking_required=best.unloading_rebooking_required,
                original_loading_window=best.original_loading_window,
                proposed_loading_window=best.proposed_loading_window,
                original_unloading_window=best.original_unloading_window,
                proposed_unloading_window=best.proposed_unloading_window,
                loading_postal_code=str(getattr(best_order.loading_location, "postal_code", "") or ""),
                unloading_postal_code=str(getattr(best_order.unloading_location, "postal_code", "") or ""),
                route_distance_km=route_result.distance_km,
                route_duration_minutes=int(route_result.duration_minutes or 0),
                route_provider=route_result.provider,
                route_estimated=bool(route_result.estimated),
                route_warning=route_result.warning,
                duty_days=max(1, (best.planned_unloading_at.date() - best.planned_loading_at.date()).days + 1),
                overnight_stop_label=(
                    getattr(best_order.unloading_location, "full_display", "")
                    if best.planned_unloading_at.date() > best.planned_loading_at.date() else ""
                ),
                start_location_id=getattr(resource, "location_id", None),
                start_location_label=getattr(resource, "location_label", "") or "Standort unbekannt",
                transfer_distance_km=(getattr(transfer_route, "distance_km", None) if transfer_route is not None else None),
                transfer_route_estimated=bool(getattr(transfer_route, "estimated", False)) if transfer_route is not None else True,
                return_to_base_required=bool(getattr(resource, "return_to_base_required", False)),
                home_base_location_id=getattr(resource, "home_base_location_id", None),
                home_base_location_label=getattr(resource, "home_base_location_label", "") or "Heimatbasis",
                return_to_base_minutes=(int(getattr(return_route, "duration_minutes", 0) or 0) if return_route is not None else 0),
                return_to_base_distance_km=(getattr(return_route, "distance_km", None) if return_route is not None else None),
                return_route_estimated=bool(getattr(return_route, "estimated", False)) if return_route is not None else False,
                projected_end_location_id=int(best_order.unloading_location_id),
                future_positioning_score=sum(
                    int(reason.rsplit("+", 1)[1]) for reason in best.reasons
                    if reason.startswith("Zukunftspositionierung:") and "+" in reason
                ),
                equivalent_best=(
                    len(ranked) > 1
                    and ranked[1].equivalent_to_best
                    and ranked[1].score.order.order_id == int(best_order.id)
                ),
            )
            if assignment.equivalent_best:
                assignment.reasons.append(
                    f"Nahezu gleichwertige Alternative innerhalb von "
                    f"{self.rules.equivalent_score_margin} Punkten vorhanden"
                )
            if assignment.route_distance_km is not None:
                marker = " (geschätzt)" if assignment.route_estimated else ""
                assignment.reasons.append(
                    f"Fahrstrecke {assignment.route_distance_km:.1f} km, "
                    f"Fahrzeit {assignment.route_duration_minutes // 60}:{assignment.route_duration_minutes % 60:02d} h{marker}"
                )
            elif assignment.route_warning:
                assignment.reasons.append(f"Entfernung nicht verfügbar: {assignment.route_warning}")
            if assignment.duty_days > 1:
                assignment.reasons.append(
                    f"Mehrtägige Tour über {assignment.duty_days} Einsatztage; "
                    f"tägliche Ruhezeit am Zwischenstandort {assignment.overnight_stop_label or 'unterwegs'} berücksichtigt"
                )
            result.assignments.append(assignment)
            assignments_by_vehicle[resource.vehicle_id] = assignments_by_vehicle.get(resource.vehicle_id, 0) + 1
            unused_vehicle_ids.discard(int(resource.vehicle_id))
            assignment_minutes = self._assignment_work_minutes(assignment, best_order)
            planned_minutes_by_vehicle[resource.vehicle_id] = planned_minutes_by_vehicle.get(resource.vehicle_id, 0) + assignment_minutes
            self._record_decision(assignment)
            remaining.remove(int(best_order.id))
            successor_id = chain_plan.successor(int(best_order.id))
            if successor_id is not None and successor_id in remaining:
                chain_owner_by_order[successor_id] = int(resource.vehicle_id)
                alternatives_count = len(chain_plan.alternative_successors(int(best_order.id)))
                assignment.reasons.append(
                    f"Folgeauftrag {orders_by_id[successor_id].order_number} für dieses Fahrzeug reserviert"
                    + (f"; aus {alternatives_count} möglichen Anschlüssen global ausgewählt" if alternatives_count > 1 else "")
                )
            working_resources = self._reserve_resource_timeline(
                working_resources,
                chosen_index=resource_index,
                assignment=assignment,
                unloading_location_id=int(best_order.unloading_location_id),
                unloading_location_label=best_order.unloading_location.full_display,
            )

        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.DAY_TOURS,
            f"{len(result.assignments)} Aufträge auf vollständige Fahrzeugtage verteilt",
            f"{len(assignments_by_vehicle)} Fahrzeuge wurden tatsächlich eingesetzt.",
            4,
        ))
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.RESOURCE_RESERVATION,
            "Fahrzeuge und Fahrer zeitlich reserviert",
            "Eine Ressource wird erst nach dem Ende ihres vorherigen Auftrags erneut angeboten.",
            5,
        ))
        result.proposed_tours = self.tour_builder.build(result.assignments)
        result.vehicle_capacities = self._build_vehicle_capacities(result, resources)
        result.suggestions = self._build_suggestions(result, resources)
        result.planning_variants = self.planning_core.build_variants(result)
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.VARIANT_EVALUATION,
            f"{len(result.planning_variants)} nachvollziehbare Planungsvarianten bewertet",
            f"Empfohlene Strategie: {result.planning_strategy.value}",
            6,
        ))
        result.planning_trace.append(self.planning_core.trace(
            PlanningPhase.COMPLETED,
            f"{result.assigned_count} von {result.orders_total} Aufträgen eingeplant",
            f"{result.proposed_tour_count} Tourvorschläge, {result.open_count} offene Aufträge",
            7,
        ))
        result.simulation_seconds = perf_counter() - started
        result.performance_metrics = {
            "candidate_evaluations": candidate_evaluations,
            "order_route_cache_entries": len(route_by_order),
            "transfer_route_cache_entries": len(transfer_route_cache),
            "transfer_route_cache_hits": transfer_cache_hits,
            "transfer_route_cache_misses": transfer_cache_misses,
            "simulation_milliseconds": round(result.simulation_seconds * 1000, 3),
        }
        return result

    @staticmethod
    def _dispatch_priority_rank(order) -> int:
        value = str(getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt") or "Eigenfuhrpark bevorzugt")
        return {
            "Eigenfuhrpark bevorzugt": 3,
            "Flexibel": 2,
            "Verkauf bevorzugt": 1,
        }.get(value, 2)

    def _highest_dispatch_priority_scores(self, all_scores):
        if not all_scores or not self.rules.protect_own_fleet_priority:
            return all_scores
        highest = max(self._dispatch_priority_rank(item[1]) for item in all_scores)
        return [item for item in all_scores if self._dispatch_priority_rank(item[1]) == highest]

    def _apply_hard_business_rules(self, score, order, route_result, *, resource, already_planned_minutes: int) -> None:
        """Reject operationally invalid assignments before any score ranking.

        A rejected candidate is never allowed back into the ranking by a high
        priority, chain or utilization bonus.
        """
        priority = str(
            getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt")
            or "Eigenfuhrpark bevorzugt"
        )
        distance = getattr(route_result, "distance_km", None)
        if distance is None:
            distance = getattr(order, "route_distance_km", None)
        try:
            distance = float(distance) if distance is not None else None
        except (TypeError, ValueError):
            distance = None

        if (
            self.rules.block_longhaul_sale_for_own_fleet
            and priority == "Verkauf bevorzugt"
            and distance is not None
            and distance > self.rules.sale_distance_threshold_km
        ):
            score.feasible = False
            score.rejection_reasons.append(
                f"Verkaufsauftrag über {self.rules.sale_distance_threshold_km:.0f} km bleibt für Subunternehmer "
                f"reserviert ({distance:.1f} km)"
            )

        return_minutes = self._return_to_base_minutes(resource, order)
        workday = self.workday_calculator.candidate(
            score=score,
            order=order,
            route_result=route_result,
            return_to_base_minutes=return_minutes,
            already_planned_minutes=already_planned_minutes,
        )
        candidate_minutes = workday.assignment_minutes

        # Nahverkehr darf den Arbeitstag nicht außerhalb der Heimatbasis beenden.
        # Mehrtägige Aufträge sind deshalb für Ressourcen mit täglicher
        # Basisrückkehr unzulässig. Zusätzlich muss auch die Rückfahrt selbst
        # noch innerhalb der aktuellen Fahrerschicht liegen.
        if getattr(resource, "return_to_base_required", False):
            available_again = getattr(score, "planned_available_at", None)
            duty_end = getattr(resource, "duty_end_at", None)
            if available_again is not None and available_again.date() > score.planned_loading_at.date():
                score.feasible = False
                score.rejection_reasons.append(
                    "Nahverkehr muss am selben Arbeitstag zur Heimatbasis zurückkehren; "
                    "der Auftrag endet erst am Folgetag"
                )
        total_minutes = workday.total_minutes
        score.reasons.append(f"Arbeitszeitbestandteile: {workday.components_text()}")
        if return_minutes:
            score.reasons.append(
                f"Verbindliche Rückfahrt zur Basis {resource.home_base_location_label or ''}: "
                f"{return_minutes // 60}:{return_minutes % 60:02d} h reserviert"
            )
        if total_minutes > self.rules.max_daily_work_minutes:
            score.feasible = False
            score.rejection_reasons.append(
                f"Arbeitszeit {total_minutes // 60}:{total_minutes % 60:02d} h überschreitet "
                f"die harte Tagesgrenze von {self.rules.max_daily_work_minutes // 60}:"
                f"{self.rules.max_daily_work_minutes % 60:02d} h"
            )

    def _return_to_base_minutes(self, resource, order) -> int:
        if not getattr(resource, "return_to_base_required", False):
            return 0
        base_id = getattr(resource, "home_base_location_id", None)
        unloading_id = getattr(order, "unloading_location_id", None)
        if not base_id or not unloading_id or int(base_id) == int(unloading_id):
            return 0
        try:
            route = self.routing_service.calculate(int(unloading_id), int(base_id))
            minutes = int(getattr(route, "duration_minutes", 0) or 0)
            if minutes > 0:
                return minutes
        except Exception:
            pass
        # Deterministic fallback mirrors the transfer fallback used by scoring.
        return int(getattr(self.scoring_engine, "TRANSFER_MINUTES", 30) or 30)

    def _candidate_work_minutes(self, score, order, route_result) -> int:
        return self.workday_calculator.candidate(
            score=score, order=order, route_result=route_result
        ).assignment_minutes

    def _assignment_work_minutes(self, assignment, order=None) -> int:
        return self.workday_calculator.assignment(assignment, order).assignment_minutes


    def _apply_state_transition_score(self, score, order, *, resource, prior_assignments: int = 0) -> None:
        """Bewertet nicht nur den Auftrag, sondern den resultierenden Tagesendzustand.

        Nahverkehr soll regionale Shuttle-Leistung übernehmen und am selben Tag
        zur Basis zurückkehren. Fernverkehr soll dagegen den Auftrag erhalten,
        dessen Endstandort sinnvoll als Ruhe-/Folgetagsstandort genutzt werden
        kann. Damit wird z. B. Germersheim→Mannheim nicht vom Nahverkehr
        blockiert, wenn ein Fernverkehrsfahrzeug auswärts pausieren darf.
        """
        operation = str(getattr(resource, "driver_operation", "") or getattr(resource, "operation_type", "") or "").casefold()
        is_local = bool(getattr(resource, "return_to_base_required", False))
        is_shuttle = str(getattr(order, "order_type", "") or "").strip().casefold() == "shuttle"
        base_id = getattr(resource, "home_base_location_id", None)
        unloading_id = getattr(order, "unloading_location_id", None)
        ends_away = bool(base_id and unloading_id and int(base_id) != int(unloading_id))

        if is_local:
            if is_shuttle:
                score.score += 110
                score.reasons.append("Nahverkehr übernimmt regionale Shuttle-Leistung +110")
            return_minutes = self._return_to_base_minutes(resource, order)
            if return_minutes:
                penalty = min(260, max(25, return_minutes * 3))
                score.score -= penalty
                score.reasons.append(
                    f"Folgezustand Nahverkehr: Basisrückkehr bindet {return_minutes} Minuten -{penalty}"
                )
        else:
            if is_shuttle:
                score.score -= 35
                score.reasons.append("Fernverkehrskapazität für passende Anschlussrelation freihalten -35")
            if ends_away:
                bonus = 180
                # Der auswärtige Fernverkehrsauftrag ist ein Tagesabschluss,
                # kein Frühstart. Zuerst werden bis zu zwei passende regionale
                # Shuttle-Umläufe genutzt; danach erhält der Mannheim-Auftrag
                # den starken Abschlussbonus.
                if not is_shuttle:
                    bonus = 40 if prior_assignments < 2 else 360
                score.score += bonus
                score.reasons.append(
                    f"Fernverkehr kann am Entladeort ruhen und dort den Folgetag beginnen +{bonus}"
                )

    def _apply_fleet_strategy_score(self, score, order, route_result) -> None:
        """Apply regional own-fleet policy before generic optimization.

        Own-fleet orders are protected by the hard tier selection above. These
        score adjustments then choose sensible work within a tier and discourage
        sending an own vehicle into long-haul work intended for sale.
        """
        priority = str(getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt") or "Eigenfuhrpark bevorzugt")
        distance = getattr(route_result, "distance_km", None)
        if distance is None:
            distance = getattr(order, "route_distance_km", None)
        try:
            distance = float(distance) if distance is not None else None
        except (TypeError, ValueError):
            distance = None

        if priority == "Eigenfuhrpark bevorzugt":
            bonus = 1200
            score.score += bonus
            score.reasons.append(f"Eigenfuhrpark-Auftrag wird verbindlich geschützt +{bonus}")
        elif priority == "Verkauf bevorzugt":
            penalty = 900
            score.score -= penalty
            score.reasons.append(f"Verkaufsauftrag erst nach Eigenfuhrpark-Aufträgen -{penalty}")

        if distance is not None and distance > self.rules.sale_distance_threshold_km:
            if priority == "Verkauf bevorzugt":
                penalty = 1400
                score.score -= penalty
                score.reasons.append(
                    f"Fernverkehr {distance:.1f} km über {self.rules.sale_distance_threshold_km:.0f} km für Subunternehmer priorisiert -{penalty}"
                )
            elif self.rules.keep_own_fleet_regional:
                penalty = min(700, 250 + round(distance - self.rules.sale_distance_threshold_km) * 3)
                score.score -= penalty
                score.reasons.append(
                    f"Eigenes Fahrzeug möglichst im Regionalverkehr halten ({distance:.1f} km) -{penalty}"
                )


    def _transfer_route_for(self, resource, order):
        loading = getattr(order, "loading_location", None)
        # Unit tests and detached preview objects must not resolve unrelated
        # database/cache routes solely from coincidentally matching numeric IDs.
        if loading is None or not hasattr(loading, "_sa_instance_state"):
            return None
        return self._route_between(
            getattr(resource, "location_id", None),
            getattr(order, "loading_location_id", None),
        )

    def _route_between(self, origin_id, destination_id):
        if not origin_id or not destination_id or int(origin_id) == int(destination_id):
            return None
        try:
            return self.routing_service.calculate(int(origin_id), int(destination_id))
        except Exception:
            return None

    def _route_for_order(self, order):
        """Berechnet die Relation einmal pro Auftrag; Tests ohne echte ORM-Orte bleiben offline."""
        loading = getattr(order, "loading_location", None)
        unloading = getattr(order, "unloading_location", None)
        if loading is None or unloading is None:
            from leipzigerflow.routing.models import RouteResult
            return RouteResult(None, 0, provider="fallback", estimated=True, warning="Lade- oder Entladeort fehlt.")
        # SimpleNamespace-Testdaten besitzen keinen SQLAlchemy-Status. In diesem Fall
        # wird bewusst kein externer Netzwerkaufruf ausgelöst.
        if not hasattr(loading, "_sa_instance_state") or not hasattr(unloading, "_sa_instance_state"):
            from leipzigerflow.routing.models import RouteResult
            return RouteResult(None, 0, provider="test", estimated=True, warning="Keine persistierten Standortdaten.")
        return self.routing_service.calculate(int(loading.id), int(unloading.id))

    @staticmethod
    def _reserve_resource_timeline(resources, *, chosen_index: int, assignment: ProposedAssignment,
                                   unloading_location_id: int, unloading_location_label: str):
        """Reserviert Fahrzeug UND Fahrer über alle überlappenden Ressourcenfenster.

        Damit können weder doppelte Tagesgrundtouren noch ein auf mehreren Fahrzeugen
        hinterlegter Fahrer parallel erneut ausgewählt werden. Nicht überlappende
        Folgeschichten desselben Fahrzeugs bleiben erhalten.
        """
        chosen = resources[chosen_index]
        updated = []
        for index, item in enumerate(resources):
            same_vehicle = int(item.vehicle_id) == int(chosen.vehicle_id)
            same_driver = (chosen.driver_id is not None and item.driver_id is not None
                           and int(item.driver_id) == int(chosen.driver_id))
            duty_start = item.duty_start_at or item.available_at
            duty_end = item.duty_end_at
            overlaps = duty_start < assignment.available_again_at and (duty_end is None or duty_end > assignment.loading_at)
            if not overlaps or not (same_vehicle or same_driver):
                updated.append(item)
                continue
            new_available = max(item.available_at, assignment.available_again_at)
            # Ist das komplette Ressourcenfenster verbraucht, bleibt es zwar zur
            # Transparenz erhalten, kann wegen available_at > duty_end aber nicht
            # mehr erfolgreich bewertet werden.
            updated.append(replace(
                item,
                available_at=new_available,
                location_id=(unloading_location_id if same_vehicle else item.location_id),
                location_label=(unloading_location_label if same_vehicle else item.location_label),
                state=ResourceState.FREE,
                source_tour_id=(item.source_tour_id if item.source_tour_id is not None else -item.vehicle_id),
                source_tour_number=(item.source_tour_number or "Neue Tour (Simulation)"),
                reason=f"Reserviert durch Auftrag {assignment.order_number} bis {assignment.available_again_at:%H:%M}.",
            ))
        return updated

    def _build_vehicle_capacities(self, result: DispatchSimulationResult, resources) -> list[VehicleCapacity]:
        shifts: dict[int, int] = {}
        labels: dict[int, str] = {}
        trailer_types: dict[int, set[str]] = {}
        for resource in resources:
            labels[resource.vehicle_id] = resource.vehicle_label
            trailer_types.setdefault(resource.vehicle_id, set()).add(resource.trailer_type or "Nicht zugeordnet")
            if resource.duty_start_at and resource.duty_end_at:
                minutes = max(0, round((resource.duty_end_at - resource.duty_start_at).total_seconds() / 60))
            else:
                minutes = 10 * 60
            shifts[resource.vehicle_id] = shifts.get(resource.vehicle_id, 0) + minutes

        planned: dict[int, int] = {}
        for item in result.assignments:
            planned[item.vehicle_id] = planned.get(item.vehicle_id, 0) + self._assignment_work_minutes(item)

        rows: list[VehicleCapacity] = []
        for vehicle_id, available in shifts.items():
            used = planned.get(vehicle_id, 0)
            free = max(0, available - used)
            utilization = min(100.0, used / available * 100.0) if available else 0.0
            additional = free // 300
            if free < 120:
                recommendation = "Praktisch ausgelastet"
            elif free < 300:
                recommendation = "Kurze regionale Zusatzfahrt prüfen"
            elif additional <= 1:
                recommendation = "Eine zusätzliche Tour kann eingekauft werden"
            else:
                recommendation = f"Bis zu {additional} zusätzliche Touren können eingekauft werden"
            rows.append(VehicleCapacity(
                vehicle_id=vehicle_id,
                vehicle_label=labels.get(vehicle_id, str(vehicle_id)),
                trailer_type=", ".join(sorted(trailer_types.get(vehicle_id, {"Nicht zugeordnet"}))),
                available_minutes=available,
                planned_minutes=used,
                free_minutes=free,
                utilization_percent=utilization,
                suggested_additional_tours=additional,
                recommendation=recommendation,
            ))
        return sorted(rows, key=lambda row: (-row.free_minutes, row.vehicle_label))

    def _build_suggestions(self, result: DispatchSimulationResult, resources) -> list[PlanningSuggestion]:
        suggestions: list[PlanningSuggestion] = []

        rebooked = [
            item for item in result.assignments
            if item.loading_rebooking_required or item.unloading_rebooking_required
        ]
        for item in rebooked:
            parts = []
            if item.loading_rebooking_required:
                parts.append(f"Laden: {item.original_loading_window} → {item.proposed_loading_window}")
            if item.unloading_rebooking_required:
                parts.append(f"Entladen: {item.original_unloading_window} → {item.proposed_unloading_window}")
            suggestions.append(PlanningSuggestion(
                category="Zeitfenster",
                title=f"Zeitfenster für Auftrag {item.order_number} umbuchen",
                description="; ".join(parts),
                benefit=f"Übernahme durch {item.vehicle_label} wird dadurch möglich.",
                affected_orders=[item.order_number],
                severity="Aktion",
            ))

        for tour in result.proposed_tours:
            if tour.order_count >= 2:
                suggestions.append(PlanningSuggestion(
                    category="Tourenbildung",
                    title=f"{tour.order_count} Aufträge auf {tour.vehicle_label} bündeln",
                    description="Reihenfolge: " + " → ".join(a.order_number for a in tour.assignments),
                    benefit="Weniger einzelne Fahrzeugstarts und bessere Tagesauslastung.",
                    affected_orders=[a.order_number for a in tour.assignments],
                ))

        vehicle_loads: dict[int, int] = {}
        vehicle_labels: dict[int, str] = {}
        for item in result.assignments:
            vehicle_labels[item.vehicle_id] = item.vehicle_label
            vehicle_loads[item.vehicle_id] = vehicle_loads.get(item.vehicle_id, 0) + self._assignment_work_minutes(item)
        if vehicle_loads:
            maximum = max(vehicle_loads.values())
            minimum = min(vehicle_loads.values())
            if len(vehicle_loads) > 1 and maximum - minimum >= 180:
                heavy = max(vehicle_loads, key=vehicle_loads.get)
                light = min(vehicle_loads, key=vehicle_loads.get)
                light_capacity = next((row for row in result.vehicle_capacities if row.vehicle_id == light), None)
                free_text = f"{light_capacity.free_minutes // 60}:{light_capacity.free_minutes % 60:02d} h" if light_capacity else "mehrere Stunden"
                suggestions.append(PlanningSuggestion(
                    category="Flottenauslastung",
                    title=f"Zusätzliche Tour für {vehicle_labels[light]} einkaufen",
                    description=(f"{vehicle_labels[heavy]} ist rund {maximum // 60} h geplant, "
                                 f"{vehicle_labels[light]} nur rund {minimum // 60} h. "
                                 f"Verbleibende Kapazität: {free_text}."),
                    benefit=(light_capacity.recommendation if light_capacity else
                             "Zusätzlichen Auftrag einkaufen oder Aufträge umverteilen, damit alle Fahrzeuge bestmöglich ausgelastet sind."),
                    severity="Aktion",
                ))

        for capacity in result.vehicle_capacities:
            if capacity.free_minutes >= 300 and capacity.utilization_percent < 75:
                suggestions.append(PlanningSuggestion(
                    category="Kapazitätseinkauf",
                    title=f"Zusätzliche Tour für {capacity.vehicle_label} suchen",
                    description=(f"Auslastung {capacity.utilization_percent:.1f} %, freie Kapazität "
                                 f"{capacity.free_minutes // 60}:{capacity.free_minutes % 60:02d} h, "
                                 f"Aufbau: {capacity.trailer_type}."),
                    benefit=capacity.recommendation,
                    severity="Aktion",
                ))

        unused = [r for r in resources if r.vehicle_id not in vehicle_loads and r.state not in {ResourceState.WORKSHOP, ResourceState.DEFECT}]
        if unused and result.unassigned:
            suggestions.append(PlanningSuggestion(
                category="Offene Aufträge",
                title="Offene Aufträge trotz freier Ressourcen prüfen",
                description=f"{len(result.unassigned)} Auftrag/Aufträge bleiben offen, obwohl {len(unused)} Ressource(n) ungenutzt sind.",
                benefit="Ablehnungsgründe wie Zeitfenster, Trailerart oder Schichtende gezielt bearbeiten.",
                affected_orders=[item.order_number for item in result.unassigned],
                severity="Warnung",
            ))
        elif result.unassigned:
            suggestions.append(PlanningSuggestion(
                category="Kapazität",
                title="Zusätzliche Kapazität erforderlich",
                description=f"{len(result.unassigned)} Auftrag/Aufträge konnten intern nicht eingeplant werden.",
                benefit="Subunternehmer, Umbuchung oder Verschiebung auf einen anderen Planungstag prüfen.",
                affected_orders=[item.order_number for item in result.unassigned],
                severity="Warnung",
            ))

        if result.vehicle_capacities and not any(item.category == "Flottenauslastung" for item in suggestions):
            free_minutes = sum(item.free_minutes for item in result.vehicle_capacities)
            additional = sum(item.suggested_additional_tours for item in result.vehicle_capacities)
            suggestions.append(PlanningSuggestion(
                category="Flottenauslastung",
                title="Verbleibende Flottenkapazität aktiv vermarkten",
                description=(f"In der geplanten Flotte verbleiben insgesamt "
                             f"{free_minutes // 60}:{free_minutes % 60:02d} h freie Kapazität."),
                benefit=(f"Voraussichtlich können noch etwa {additional} zusätzliche Tour(en) "
                         "eingekauft werden." if additional else "Nur kurze Zusatzfahrten prüfen."),
                severity="Aktion" if additional else "Hinweis",
            ))

        if not suggestions and result.assignments:
            suggestions.append(PlanningSuggestion(
                category="Planqualität",
                title="Keine wesentlichen Eingriffe erforderlich",
                description="Die Simulation konnte alle geprüften Aufträge ohne auffällige Zielkonflikte einplanen.",
                benefit="Planung kann nach fachlicher Kontrolle übernommen werden.",
            ))
        return suggestions

    def _append_unassigned(self, result, remaining, candidates, scores_by_order) -> None:
        for order_id in sorted(remaining):
            candidate = candidates[order_id]
            evaluated = scores_by_order[order_id]
            rejection_reasons: list[str] = []
            for score in evaluated:
                rejection_reasons.extend(score.rejection_reasons)
            reasons = list(dict.fromkeys(rejection_reasons)) or [
                "Keine geeignete interne Ressource verfügbar"
            ]
            result.unassigned.append(
                UnassignedOrder(
                    order_id=order_id,
                    order_number=candidate.order_number,
                    priority_score=candidate.priority_score,
                    reasons=reasons,
                    alternatives=self._alternatives(evaluated),
                )
            )

    def _record_decision(self, assignment: ProposedAssignment) -> None:
        if self.history_store is None:
            return
        alternatives = [
            f"{item.vehicle_label}: {item.score} Punkte – {'; '.join(item.reasons)}"
            for item in assignment.alternatives
        ]
        self.history_store.append(
            DecisionHistoryEntry(
                created_at=datetime.now(),
                order_id=assignment.order_id,
                order_number=assignment.order_number,
                selected_vehicle_id=assignment.vehicle_id,
                selected_vehicle_label=assignment.vehicle_label,
                selected_score=assignment.score,
                confidence_percent=assignment.confidence_percent,
                decision=assignment.mode.value,
                reasons=assignment.reasons,
                rejected_alternatives=alternatives,
            )
        )

    def _alternatives(self, scores) -> list[AlternativeAssignment]:
        sorted_scores = sorted(
            scores,
            key=lambda score: (
                score.feasible,
                score.score,
                -(score.planned_loading_at.timestamp() if score.planned_loading_at else 0),
            ),
            reverse=True,
        )
        return [
            AlternativeAssignment(
                vehicle_label=score.resource.vehicle_label,
                driver_label=score.resource.driver_label,
                score=score.score,
                feasible=score.feasible,
                loading_at=score.planned_loading_at,
                mode=score.mode,
                reasons=(score.reasons if score.feasible else score.rejection_reasons),
            )
            for score in sorted_scores[: self.MAX_ALTERNATIVES + 1]
        ]
