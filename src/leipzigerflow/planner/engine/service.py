from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from leipzigerflow.models.tour import Tour
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.vehicle_staffing_profile import VehicleStaffingProfile
from leipzigerflow.services.tour_service import TourService
from leipzigerflow.services.daily_tour_service import DailyTourService
from leipzigerflow.planner.engine.availability import ResourceAvailabilityEngine
from leipzigerflow.planner.engine.configuration import DispatchConfigurationStore
from leipzigerflow.planner.engine.dispatcher import AutomaticDispatcher
from leipzigerflow.planner.engine.models import PlanningStrategy, PlanningVariant
from leipzigerflow.planner.engine.rules import DispatchRuleStore


class DispatchSimulationService:
    VARIANT_STRATEGIES = (
        ("Variante A · Empfohlen", PlanningStrategy.MAX_UTILIZATION,
         "Eigenfuhrpark, regionale Tagesleistung und wirtschaftliche Arbeitszeitauslastung."),
        ("Variante B · Wenig Leerfahrt", PlanningStrategy.MIN_EMPTY_RUN,
         "Bevorzugt kurze Anfahrten und minimiert unproduktive Kilometer."),
        ("Variante C · Gleichmäßig", PlanningStrategy.BALANCED_FLEET,
         "Verteilt die zulässige Tagesarbeit möglichst gleichmäßig auf die Fahrzeuge."),
        ("Variante D · Eigenfuhrpark", PlanningStrategy.OWN_FLEET_FIRST,
         "Maximiert die Abdeckung eigenfuhrpark-priorisierter Aufträge."),
    )

    def __init__(self, session):
        self.session = session
        self.availability_engine = ResourceAvailabilityEngine()
        self.configuration_store = DispatchConfigurationStore()
        self.rule_store = DispatchRuleStore()

    def _load_input(self, planning_day: date):
        DailyTourService(self.session).ensure_for_day(planning_day)
        vehicles = list(self.session.scalars(
            select(Vehicle)
            .options(
                joinedload(Vehicle.home_base_location),
                joinedload(Vehicle.staffing_profile).joinedload(VehicleStaffingProfile.primary_driver).joinedload(Driver.home_base_location),
                joinedload(Vehicle.staffing_profile).joinedload(VehicleStaffingProfile.relief_driver).joinedload(Driver.home_base_location),
            )
            .where(Vehicle.active.is_(True))
        ).unique())
        tours = list(
            self.session.scalars(
                select(Tour)
                .options(
                    joinedload(Tour.driver), joinedload(Tour.vehicle),
                    selectinload(Tour.positions).joinedload(TourPosition.transport_order).joinedload(TransportOrder.loading_location),
                    selectinload(Tour.positions).joinedload(TourPosition.transport_order).joinedload(TransportOrder.unloading_location),
                )
                .where(Tour.tour_date <= planning_day)
            ).unique()
        )
        assigned_ids = select(TourPosition.transport_order_id)
        orders = list(self.session.scalars(
            select(TransportOrder)
            .options(joinedload(TransportOrder.customer), joinedload(TransportOrder.loading_location), joinedload(TransportOrder.unloading_location))
            .where(~TransportOrder.id.in_(assigned_ids), TransportOrder.status.notin_(("Erledigt", "Storniert")), TransportOrder.loading_date == planning_day)
            .order_by(TransportOrder.loading_date, TransportOrder.order_number)
        ))
        return self.availability_engine.build(vehicles, tours, planning_day), orders

    @staticmethod
    def _variant_metrics(result):
        per_vehicle: dict[int, int] = {}
        total_minutes = 0
        total_distance = 0.0
        has_distance = False
        for a in result.assignments:
            minutes = max(0, int(a.transfer_minutes or 0)) + max(0, int(a.waiting_minutes or 0)) + max(0, int(a.route_duration_minutes or 0)) + 120
            per_vehicle[a.vehicle_id] = per_vehicle.get(a.vehicle_id, 0) + minutes
            total_minutes += minutes
            if a.route_distance_km is not None:
                total_distance += float(a.route_distance_km)
                has_distance = True
        own_assigned = sum(1 for a in result.assignments if any("Eigenfuhrpark" in r for r in a.reasons))
        max_minutes = max(per_vehicle.values(), default=0)
        spread = (max(per_vehicle.values()) - min(per_vehicle.values())) if len(per_vehicle) > 1 else 0
        score = 100
        score -= result.open_count * 12
        score -= result.subcontractor_count * 2
        score -= min(18, result.total_transfer_minutes // 15)
        score -= min(10, spread // 45)
        score += min(8, own_assigned * 2)
        if max_minutes > 600:
            score = 0
        reasons = [
            f"{result.assigned_count} von {result.orders_total} Aufträgen intern eingeplant",
            f"{result.open_count} Auftrag/Aufträge bleiben offen",
            f"{result.total_transfer_minutes} Minuten Leeranfahrt",
            f"Höchste Fahrzeugarbeitszeit {max_minutes // 60}:{max_minutes % 60:02d} h",
        ]
        return max(0, min(100, score)), total_minutes, (total_distance if has_distance else None), max_minutes, reasons

    def simulate(self, planning_day: date):
        resources, orders = self._load_input(planning_day)
        rules = self.rule_store.load()
        weights = self.configuration_store.load()
        results = []
        variants = []
        for index, (name, strategy, description) in enumerate(self.VARIANT_STRATEGIES):
            dispatcher = AutomaticDispatcher(weights=weights, rules=rules)
            result = dispatcher.simulate(resources, orders, planning_day, strategy=strategy)
            score, total_minutes, distance, max_minutes, reasons = self._variant_metrics(result)
            variant = PlanningVariant(
                name=name, strategy=strategy, score=score,
                vehicle_count=result.utilized_vehicle_count,
                tour_count=result.proposed_tour_count,
                assigned_orders=result.assigned_count,
                total_minutes=total_minutes,
                total_distance_km=distance,
                description=description,
                recommended=False,
                open_orders=result.open_count,
                subcontractor_orders=result.subcontractor_count,
                empty_run_minutes=result.total_transfer_minutes,
                max_vehicle_minutes=max_minutes,
                reasons=reasons,
                simulation_result=result,
            )
            results.append(result); variants.append(variant)
        # Recommended: highest score, then more own/internal orders, then less empty run.
        best_index = max(range(len(variants)), key=lambda i: (variants[i].score, variants[i].assigned_orders, -variants[i].empty_run_minutes))
        variants[best_index].recommended = True
        variants.sort(key=lambda v: (not v.recommended, -v.score, -v.assigned_orders, v.empty_run_minutes))
        primary = variants[0].simulation_result
        primary.planning_variants = variants
        primary.planning_strategy = variants[0].strategy
        return primary, resources, weights

    def apply(self, result, planning_day: date) -> tuple[int, int]:
        tour_service = TourService(self.session)
        created_tours = 0
        assigned_orders = 0
        for proposal in getattr(result, "proposed_tours", []) or []:
            tour = None
            source_id = getattr(proposal, "source_tour_id", None)
            if source_id and int(source_id) > 0:
                tour = tour_service.get(int(source_id))
            if tour is not None and getattr(tour, "planning_locked", False):
                continue
            if tour is None:
                tour = tour_service.create({
                    "tour_date": proposal.assignments[0].loading_date if proposal.assignments and getattr(proposal.assignments[0], "loading_date", None) else planning_day,
                    "planned_start_time": proposal.planned_start_at.time() if proposal.planned_start_at is not None else None,
                    "status": "Geplant", "driver_id": proposal.driver_id, "vehicle_id": proposal.vehicle_id,
                    "remarks": f"Automatisch aus {getattr(result.planning_strategy, 'value', 'Planungsvariante')} angelegt",
                })
                created_tours += 1
            for assignment in proposal.assignments:
                order = self.session.get(TransportOrder, int(assignment.order_id))
                if order is None or any(p.transport_order_id == order.id for p in tour.positions):
                    continue
                tour = tour_service.add_order(tour, order)
                assigned_orders += 1
        return created_tours, assigned_orders
