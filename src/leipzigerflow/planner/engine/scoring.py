from __future__ import annotations

from datetime import datetime, timedelta

from leipzigerflow.planner.engine.context import FleetPlanningContext
from leipzigerflow.planner.engine.models import (
    AssignmentMode,
    AssignmentScore,
    DispatchWeights,
    VehicleClass,
)
from leipzigerflow.planner.engine.rules import DispatchRules
from leipzigerflow.planner.time_planning import TimePlanningEngine
from leipzigerflow.planner.engine.trailer_state import BaseTrailerPolicy, TrailerLocationKind


MEGA_TYPES = {"Mega-Plane", "Mega-Koffer", "Mega-Kühler"}
STANDARD_COUNTERPART = {
    "Mega-Plane": "Plane",
    "Mega-Koffer": "Koffer",
    "Mega-Kühler": "Kühler",
}


class AssignmentScoringEngine:
    TRANSFER_MINUTES = 30

    def __init__(
        self,
        time_engine: TimePlanningEngine | None = None,
        weights: DispatchWeights | None = None,
        rules: DispatchRules | None = None,
    ):
        self.time_engine = time_engine or TimePlanningEngine()
        self.weights = weights or DispatchWeights()
        self.rules = rules or DispatchRules()
        self.rules.validate()
        self.trailer_policy = BaseTrailerPolicy()

    def evaluate(
        self,
        resource,
        order,
        candidate,
        context: FleetPlanningContext | None = None,
        route_result=None,
        transfer_route_result=None,
    ) -> AssignmentScore:
        context = context or FleetPlanningContext()
        score = self.weights.normalized(self.weights.priority, candidate.priority_score)
        reasons = [f"Priorität gewichtet: {score} Punkte"] + list(candidate.priority_reasons)
        customer = getattr(order, "customer", None)
        customer_priority = max(1, min(10, int(getattr(customer, "disposition_priority", 5) or 5)))
        customer_points = customer_priority * 12
        score += customer_points
        reasons.append(f"Kundenpriorität {customer_priority}/10 +{customer_points}")
        if bool(getattr(customer, "own_fleet_preferred", False)):
            score += 80
            reasons.append("Kundenrichtlinie: Eigenfuhrpark bevorzugt +80")
        rejection: list[str] = []

        mode = AssignmentMode.EXTEND_TOUR if resource.source_tour_id is not None else AssignmentMode.NEW_TOUR

        # HARD RULES
        if resource.state.value in {"Werkstatt", "Defekt"}:
            rejection.append(f"Fahrzeugstatus: {resource.state.value}")

        if candidate.required_vehicle_class is VehicleClass.MEGA and resource.vehicle_class is not VehicleClass.MEGA:
            rejection.append("Mega-Zugmaschine und Mega-Trailer erforderlich")

        accepted_types = set(candidate.required_trailer_types)
        actual = resource.trailer_type or ""

        trailer_location_kind = str(getattr(resource, "trailer_location_kind", "") or "")
        if trailer_location_kind == TrailerLocationKind.INVALID_CUSTOMER.value:
            rejection.append("Trailer darf nicht beim Kunden abgestellt oder übernommen werden")

        if bool(getattr(resource, "trailer_change_required", False)):
            at_home_base = bool(
                resource.location_id is not None
                and resource.home_base_location_id is not None
                and int(resource.location_id) == int(resource.home_base_location_id)
            )
            change = self.trailer_policy.validate_change(
                at_home_base=at_home_base,
                loaded=bool(getattr(resource, "trailer_loaded", False)),
            )
            if not change.allowed:
                rejection.append(change.reason)
            else:
                score -= change.penalty_points
                reasons.append(f"{change.reason} -{change.penalty_points}")
        # In der vorhandenen Disposition gilt ein Standard-Koffer für einen
        # Standard-Plane-Auftrag als technisch nutzbar, sofern keine
        # Mega-Anforderung besteht. Damit kann das Fernverkehrsfahrzeug den
        # Mannheim-Auftrag übernehmen und dort die tägliche Ruhezeit einlegen.
        standard_box_covers_curtainsider = (
            actual == "Koffer"
            and accepted_types == {"Plane"}
            and candidate.required_vehicle_class is not VehicleClass.MEGA
        )
        if actual not in accepted_types and not standard_box_covers_curtainsider:
            actual_label = actual or "kein Trailer gekoppelt"
            expected = ", ".join(candidate.required_trailer_types)
            rejection.append(f"Einer der Trailertypen {expected} erforderlich; vorhanden: {actual_label}")
        elif not rejection:
            if standard_box_covers_curtainsider:
                reasons.append("Standard-Koffer für Standard-Plane-Auftrag freigegeben")
            points = self.weights.normalized(self.weights.vehicle_compatibility, 20)
            score += points
            reasons.append(f"Trailertyp {actual} kompatibel +{points}")

        same_location = resource.location_id == int(order.loading_location_id)
        transfer_minutes = 0
        if not same_location:
            transfer_minutes = int(getattr(transfer_route_result, "duration_minutes", 0) or 0)
            if transfer_minutes <= 0:
                transfer_minutes = self.TRANSFER_MINUTES
                reasons.append(
                    f"Leerfahrt zum ersten Ladeort mangels Routingwert mit {transfer_minutes} Minuten geschätzt"
                )
            else:
                reasons.append(f"Leerfahrt zum ersten Ladeort aus Routing: {transfer_minutes} Minuten")
        if transfer_minutes > self.rules.max_empty_run_minutes:
            rejection.append(
                f"Anfahrt {transfer_minutes} Minuten überschreitet Regelgrenze von "
                f"{self.rules.max_empty_run_minutes} Minuten"
            )
        resource_start = max(
            resource.available_at,
            resource.duty_start_at or resource.available_at,
        )
        arrival = resource_start + timedelta(minutes=transfer_minutes)

        def window_text(day, start_value, end_value):
            if not start_value and not end_value:
                return "offen"
            return f"{day:%d.%m.%Y} {(start_value.strftime('%H:%M') if start_value else 'offen')}–{(end_value.strftime('%H:%M') if end_value else 'offen')}"

        booked_loading_start = datetime.combine(order.loading_date, order.loading_time_from) if order.loading_time_from else datetime.combine(order.loading_date, datetime.min.time())
        booked_loading_end = datetime.combine(order.loading_date, order.loading_time_until) if order.loading_time_until else None
        location_open_start, location_open_end = self.time_engine._opening_window(order.loading_location, order.loading_date)
        flexible_loading = bool(getattr(order, "loading_time_flexible", False))
        explicit_open_start = getattr(order, "loading_open_from", None)
        explicit_open_end = getattr(order, "loading_open_until", None)
        hard_loading_start = datetime.combine(order.loading_date, explicit_open_start) if flexible_loading and explicit_open_start else (location_open_start if flexible_loading else booked_loading_start)
        hard_loading_end = datetime.combine(order.loading_date, explicit_open_end) if flexible_loading and explicit_open_end else (location_open_end if flexible_loading else booked_loading_end)
        if hard_loading_start is None:
            hard_loading_start = booked_loading_start
        loading_at = max(arrival, hard_loading_start)
        if not flexible_loading:
            loading_at = max(loading_at, booked_loading_start)
        waiting_minutes = max(0, round((loading_at - arrival).total_seconds() / 60))
        if hard_loading_end is not None and loading_at > hard_loading_end:
            rejection.append(f"Ladezeitfenster nicht erreichbar ({loading_at:%d.%m. %H:%M})")

        booked_loading_duration = 60
        if order.loading_time_from and order.loading_time_until:
            booked_loading_duration = max(1, round((datetime.combine(order.loading_date, order.loading_time_until)-datetime.combine(order.loading_date, order.loading_time_from)).total_seconds()/60))
        proposed_loading_end = loading_at + timedelta(minutes=booked_loading_duration)
        loading_rebooking = flexible_loading and order.loading_time_from is not None and loading_at.time().replace(second=0, microsecond=0) != order.loading_time_from.replace(second=0, microsecond=0)
        if loading_rebooking:
            shift_minutes = abs(round((loading_at - booked_loading_start).total_seconds()/60))
            penalty = min(20, max(2, shift_minutes // 60 * 3 or 2))
            score -= penalty
            reasons.append(f"Umbuchung Ladezeitfenster auf {loading_at:%H:%M} Uhr erforderlich -{penalty}")
        elif not rejection:
            points = self.weights.normalized(self.weights.time_window, 30)
            score += points
            reasons.append(f"Gebuchtes Ladezeitfenster erreichbar +{points}")

        loading_minutes = max(0, int(getattr(order.loading_location, "loading_duration_minutes", 60) or 60))
        unloading_minutes = max(0, int(getattr(order.unloading_location, "unloading_duration_minutes", 60) or 60))
        route_minutes = int(getattr(route_result, "duration_minutes", 0) or 0)
        if route_minutes <= 0:
            route_minutes = self.TRANSFER_MINUTES
            reasons.append(
                f"Fahrzeit Laden–Entladen mangels Routingwert mit {route_minutes} Minuten geschätzt"
            )
        else:
            reasons.append(f"Fahrzeit Laden–Entladen aus Routing: {route_minutes} Minuten")
        unload_arrival = loading_at + timedelta(minutes=loading_minutes + route_minutes)
        booked_unload_start = datetime.combine(order.unloading_date, order.unloading_time_from) if order.unloading_time_from else datetime.combine(order.unloading_date, datetime.min.time())
        booked_unload_end = datetime.combine(order.unloading_date, order.unloading_time_until) if order.unloading_time_until else None
        location_unload_start, location_unload_end = self.time_engine._opening_window(order.unloading_location, order.unloading_date)
        flexible_unloading = bool(getattr(order, "unloading_time_flexible", False))
        unload_open_from = getattr(order, "unloading_open_from", None)
        unload_open_until = getattr(order, "unloading_open_until", None)
        hard_unload_start = datetime.combine(order.unloading_date, unload_open_from) if flexible_unloading and unload_open_from else (location_unload_start if flexible_unloading else booked_unload_start)
        hard_unload_end = datetime.combine(order.unloading_date, unload_open_until) if flexible_unloading and unload_open_until else (location_unload_end if flexible_unloading else booked_unload_end)
        if hard_unload_start is None:
            hard_unload_start = booked_unload_start
        unloading_at = max(unload_arrival, hard_unload_start)
        if not flexible_unloading:
            unloading_at = max(unloading_at, booked_unload_start)
        if hard_unload_end is not None and unloading_at > hard_unload_end:
            rejection.append(f"Entladezeitfenster nicht erreichbar ({unloading_at:%d.%m. %H:%M})")
        unloading_rebooking = flexible_unloading and order.unloading_time_from is not None and unloading_at.time().replace(second=0, microsecond=0) != order.unloading_time_from.replace(second=0, microsecond=0)
        if unloading_rebooking:
            shift_minutes = abs(round((unloading_at - booked_unload_start).total_seconds()/60))
            penalty = min(20, max(2, shift_minutes // 60 * 3 or 2))
            score -= penalty
            reasons.append(f"Umbuchung Entladezeitfenster auf {unloading_at:%H:%M} Uhr erforderlich -{penalty}")

        total_duration_minutes = round((unloading_at + timedelta(minutes=unloading_minutes) - loading_at).total_seconds()/60)
        is_multi_day = unloading_at.date() > loading_at.date()
        if not is_multi_day and total_duration_minutes > self.rules.max_tour_duration_minutes:
            rejection.append(
                f"Tourdauer {total_duration_minutes} Minuten überschreitet Regelgrenze von "
                f"{self.rules.max_tour_duration_minutes} Minuten"
            )
        elif is_multi_day:
            # Calendar duration is not a continuous shift. The detailed time
            # planner inserts the daily rest and evaluates each duty day
            # separately; therefore the overnight waiting period must not make
            # the order infeasible here.
            reasons.append("Mehrtägiger Auftrag: tägliche Ruhezeit wird zwischen den Einsatztagen berücksichtigt")
        available_again = unloading_at + timedelta(minutes=unloading_minutes)
        if (
            resource.duty_end_at is not None
            and available_again > resource.duty_end_at
            and not is_multi_day
        ):
            rejection.append(
                f"Fahrerschicht endet um {resource.duty_end_at:%H:%M}; "
                f"Auftrag würde erst um {available_again:%H:%M} enden"
            )

        # SOFT RULES
        if resource.location_id and resource.location_id == int(order.loading_location_id):
            points = self.weights.normalized(self.weights.location_match, 25)
            score += points
            reasons.append(f"Fahrzeug bereits an der Ladestelle +{points}")
        elif resource.location_id is None:
            penalty = self.weights.normalized(self.weights.minimize_empty_run, 8)
            score -= penalty
            reasons.append(f"aktueller Standort unbekannt -{penalty}")
        else:
            points = self.weights.normalized(self.weights.minimize_empty_run, 8)
            score += points
            reasons.append(f"Anfahrt vorläufig {transfer_minutes} Minuten +{points}")

        if resource.driver_id is None:
            penalty = self.weights.normalized(self.weights.keep_driver, 12)
            score -= penalty
            reasons.append(f"Fahrer noch nicht zugeordnet -{penalty}")
        else:
            points = self.weights.normalized(self.weights.keep_driver, 10)
            score += points
            reasons.append(f"Fahrer aus vorheriger Tour bleibt eingesetzt +{points}")

        if mode is AssignmentMode.EXTEND_TOUR and self.rules.merge_tours:
            points = self.weights.normalized(self.weights.extend_existing_tour, 18)
            score += points
            reasons.append(f"Bestehende Tour wird erweitert +{points}")
            stability = self.weights.normalized(self.weights.planning_stability, 8)
            score += stability
            reasons.append(f"Bestehende Planung bleibt stabil +{stability}")
        else:
            reasons.append("Neue Tour erforderlich")

        # Existing coupling is operationally preferable because no recoupling is needed.
        if actual:
            points = self.weights.normalized(self.weights.avoid_recoupling, 8)
            score += points
            reasons.append(f"Bereits gekoppelter Trailer bleibt am Fahrzeug +{points}")

        # Preserve special/rare resources where a less restrictive accepted type exists.
        if actual in MEGA_TYPES:
            standard = STANDARD_COUNTERPART.get(actual)
            if standard in accepted_types:
                scarcity = context.scarcity(actual)
                penalty_base = 8 + round(12 * scarcity)
                penalty = self.weights.normalized(self.weights.resource_reserve, penalty_base)
                score -= penalty
                reasons.append(f"Mega-Ressource für zwingende Mega-Aufträge reservieren -{penalty}")
        else:
            mega_variant = f"Mega-{actual}" if actual in {"Plane", "Koffer", "Kühler"} else ""
            if mega_variant in accepted_types:
                bonus = self.weights.normalized(self.weights.resource_reserve, 12)
                score += bonus
                reasons.append(f"Standardressource genutzt, {mega_variant} bleibt frei +{bonus}")

        # Reward a resource that becomes available again early within the horizon.
        horizon_end = datetime.combine(order.loading_date + timedelta(days=self.rules.planning_horizon_days), datetime.max.time())
        if available_again <= horizon_end:
            hours_until_free = max(0.0, (available_again - loading_at).total_seconds() / 3600)
            base = max(0, 10 - round(hours_until_free))
            if base:
                points = self.weights.normalized(self.weights.followup_potential, base)
                score += points
                reasons.append(f"Frühe Anschlussverfügbarkeit +{points}")

        if waiting_minutes:
            waiting_penalty = min(20, max(1, waiting_minutes // 30))
            score -= waiting_penalty
            reasons.append(f"Wartezeit {waiting_minutes} Minuten -{waiting_penalty}")

        return AssignmentScore(
            resource=resource,
            order=candidate,
            score=score,
            feasible=not rejection,
            planned_loading_at=loading_at,
            planned_available_at=available_again,
            mode=mode,
            transfer_minutes=transfer_minutes,
            waiting_minutes=waiting_minutes,
            reasons=reasons,
            rejection_reasons=rejection,
            planned_unloading_at=unloading_at,
            loading_rebooking_required=loading_rebooking,
            unloading_rebooking_required=unloading_rebooking,
            original_loading_window=window_text(order.loading_date, order.loading_time_from, order.loading_time_until),
            proposed_loading_window=f"{loading_at:%d.%m.%Y %H:%M}–{proposed_loading_end:%H:%M}",
            original_unloading_window=window_text(order.unloading_date, order.unloading_time_from, order.unloading_time_until),
            proposed_unloading_window=f"{unloading_at:%d.%m.%Y %H:%M}",
        )
