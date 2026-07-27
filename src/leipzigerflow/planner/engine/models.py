from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum




class TourSegmentType(StrEnum):
    START_EMPTY_RUN = "Leerfahrt zur Ladestelle"
    EMPTY_RUN = "Leerfahrt"
    TRANSPORT = "Transport"
    RETURN_TO_BASE = "Rückfahrt zur Basis"


@dataclass(slots=True)
class ProposedTourSegment:
    segment_type: TourSegmentType
    started_at: datetime
    ended_at: datetime
    origin_label: str
    destination_label: str
    duration_minutes: int
    distance_km: float | None = None
    order_number: str = ""
    estimated: bool = False

    @property
    def title(self) -> str:
        return f"{self.origin_label} → {self.destination_label}"


class ResourceState(StrEnum):
    FREE = "Frei"
    ON_TOUR = "Unterwegs"
    LOADING = "Belädt"
    UNLOADING = "Entlädt"
    WAITING = "Wartet auf Zeitfenster"
    BREAK = "Pause"
    REST = "Ruhezeit"
    WORKSHOP = "Werkstatt"
    DEFECT = "Defekt"


class VehicleClass(StrEnum):
    STANDARD = "Standard"
    MEGA = "Mega"


class PlanningStrategy(StrEnum):
    MAX_UTILIZATION = "Maximale Fahrzeugauslastung"
    MIN_DISTANCE = "Minimale Kilometer"
    MIN_WORK_TIME = "Minimale Arbeitszeit"
    MIN_EMPTY_RUN = "Minimale Leerkilometer"
    OWN_FLEET_FIRST = "Maximale Tourenanzahl mit Eigenfuhrpark"
    AVOID_SUBCONTRACTORS = "Minimale Nutzung von Fremdfahrzeugen"
    BALANCED_FLEET = "Ausgewogene Auslastung der gesamten Flotte"


class PlanningPhase(StrEnum):
    DAY_ANALYSIS = "Tagesanalyse"
    CAPACITY_ANALYSIS = "Kapazitätsanalyse"
    INITIAL_WAVE = "Gleichzeitige Tourstarts"
    DAY_TOURS = "Komplette Tagestouren"
    RESOURCE_RESERVATION = "Ressourcenreservierung"
    VARIANT_EVALUATION = "Variantenbewertung"
    COMPLETED = "Planung abgeschlossen"


class AssignmentMode(StrEnum):
    EXTEND_TOUR = "Bestehende Tour erweitern"
    NEW_TOUR = "Neue Tour bilden"


@dataclass(slots=True)
class DispatchWeights:
    """Konfigurierbare Gewichtungen der deterministischen Disposition."""

    priority: int = 100
    time_window: int = 100
    location_match: int = 85
    vehicle_compatibility: int = 100
    keep_driver: int = 60
    extend_existing_tour: int = 80
    minimize_empty_run: int = 75
    avoid_subcontractor: int = 90
    resource_reserve: int = 100
    avoid_recoupling: int = 80
    followup_potential: int = 70
    planning_stability: int = 100

    def normalized(self, value: int, base: int) -> int:
        return round(base * max(0, value) / 100)


@dataclass(slots=True)
class ResourceAvailability:
    vehicle_id: int
    vehicle_label: str
    driver_id: int | None
    driver_label: str
    available_at: datetime
    location_id: int | None
    location_label: str
    state: ResourceState
    vehicle_class: VehicleClass
    trailer_type: str = ""
    source_tour_id: int | None = None
    source_tour_number: str = ""
    reason: str = ""
    duty_start_at: datetime | None = None
    duty_end_at: datetime | None = None
    shift_label: str = ""
    return_to_base_required: bool = False
    home_base_location_id: int | None = None
    home_base_location_label: str = ""
    operation_type: str = ""
    driver_operation: str = ""


@dataclass(slots=True)
class OrderCandidate:
    order_id: int
    order_number: str
    priority_score: int
    priority_reasons: list[str] = field(default_factory=list)
    required_vehicle_class: VehicleClass = VehicleClass.STANDARD
    required_trailer_types: tuple[str, ...] = ("Plane",)


@dataclass(slots=True)
class AssignmentScore:
    resource: ResourceAvailability
    order: OrderCandidate
    score: int
    feasible: bool
    planned_loading_at: datetime | None
    planned_available_at: datetime | None
    mode: AssignmentMode
    transfer_minutes: int = 0
    waiting_minutes: int = 0
    reasons: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    planned_unloading_at: datetime | None = None
    loading_rebooking_required: bool = False
    unloading_rebooking_required: bool = False
    original_loading_window: str = ""
    proposed_loading_window: str = ""
    original_unloading_window: str = ""
    proposed_unloading_window: str = ""


@dataclass(slots=True)
class AlternativeAssignment:
    vehicle_label: str
    driver_label: str
    score: int
    feasible: bool
    loading_at: datetime | None
    mode: AssignmentMode
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProposedAssignment:
    vehicle_id: int
    vehicle_label: str
    driver_id: int | None
    driver_label: str
    order_id: int
    order_number: str
    score: int
    loading_at: datetime
    available_again_at: datetime
    mode: AssignmentMode
    source_tour_id: int | None = None
    source_tour_number: str = ""
    transfer_minutes: int = 0
    waiting_minutes: int = 0
    reasons: list[str] = field(default_factory=list)
    alternatives: list[AlternativeAssignment] = field(default_factory=list)
    confidence_percent: int = 0
    confidence_label: str = "Nicht bewertet"
    equivalent_best: bool = False
    proposed_tour_position: int = 0
    loading_location_label: str = ""
    unloading_location_label: str = ""
    loading_date: object | None = None
    unloading_date: object | None = None
    required_trailer_types: str = ""
    unloading_at: datetime | None = None
    loading_rebooking_required: bool = False
    unloading_rebooking_required: bool = False
    original_loading_window: str = ""
    proposed_loading_window: str = ""
    original_unloading_window: str = ""
    proposed_unloading_window: str = ""
    loading_postal_code: str = ""
    unloading_postal_code: str = ""
    route_distance_km: float | None = None
    route_duration_minutes: int = 0
    route_provider: str = ""
    route_estimated: bool = False
    route_warning: str = ""
    duty_days: int = 1
    overnight_stop_label: str = ""
    start_location_id: int | None = None
    start_location_label: str = ""
    transfer_distance_km: float | None = None
    transfer_route_estimated: bool = False
    return_to_base_required: bool = False
    home_base_location_id: int | None = None
    home_base_location_label: str = ""
    return_to_base_minutes: int = 0
    return_to_base_distance_km: float | None = None
    return_route_estimated: bool = False


@dataclass(slots=True)
class ProposedTour:
    proposal_number: str
    vehicle_id: int
    vehicle_label: str
    driver_id: int | None
    driver_label: str
    source_tour_id: int | None = None
    source_tour_number: str = ""
    assignments: list[ProposedAssignment] = field(default_factory=list)
    cluster_label: str = ""
    cluster_score: int = 0
    cluster_reasons: list[str] = field(default_factory=list)
    total_distance_km: float | None = None
    total_route_minutes: int = 0
    distance_estimated: bool = False
    quality_score: int = 0
    quality_reasons: list[str] = field(default_factory=list)
    empty_transfer_minutes: int = 0
    overnight_count: int = 0
    segments: list[ProposedTourSegment] = field(default_factory=list)

    @property
    def order_count(self) -> int:
        return len(self.assignments)

    @property
    def planned_start_at(self):
        if self.segments:
            return self.segments[0].started_at
        return self.assignments[0].loading_at if self.assignments else None

    @property
    def planned_end_at(self):
        if self.segments:
            return self.segments[-1].ended_at
        return self.assignments[-1].available_again_at if self.assignments else None

    @property
    def average_score(self) -> float:
        if not self.assignments:
            return 0.0
        return sum(item.score for item in self.assignments) / len(self.assignments)


@dataclass(slots=True)
class UnassignedOrder:
    order_id: int
    order_number: str
    priority_score: int
    reasons: list[str]
    alternatives: list[AlternativeAssignment] = field(default_factory=list)
    subcontractor_recommended: bool = True


@dataclass(slots=True)
class PlanningSuggestion:
    category: str
    title: str
    description: str
    benefit: str = ""
    affected_orders: list[str] = field(default_factory=list)
    severity: str = "Hinweis"


@dataclass(slots=True)
class VehicleCapacity:
    vehicle_id: int
    vehicle_label: str
    trailer_type: str
    available_minutes: int
    planned_minutes: int
    free_minutes: int
    utilization_percent: float
    suggested_additional_tours: int
    recommendation: str




@dataclass(slots=True)
class PlanningTraceEntry:
    sequence: int
    phase: PlanningPhase
    message: str
    details: str = ""


@dataclass(slots=True)
class PlanningVariant:
    name: str
    strategy: PlanningStrategy
    score: int
    vehicle_count: int
    tour_count: int
    assigned_orders: int
    total_minutes: int
    total_distance_km: float | None = None
    description: str = ""
    recommended: bool = False
    open_orders: int = 0
    subcontractor_orders: int = 0
    empty_run_minutes: int = 0
    max_vehicle_minutes: int = 0
    reasons: list[str] = field(default_factory=list)
    simulation_result: object | None = None

@dataclass(slots=True)
class DispatchSimulationResult:
    created_at: datetime
    assignments: list[ProposedAssignment] = field(default_factory=list)
    unassigned: list[UnassignedOrder] = field(default_factory=list)
    resources_total: int = 0
    orders_total: int = 0
    simulation_seconds: float = 0.0
    optimization_profile: str = "Ausgewogene Planung"
    replanning_reasons: list[str] = field(default_factory=list)
    proposed_tours: list[ProposedTour] = field(default_factory=list)
    suggestions: list[PlanningSuggestion] = field(default_factory=list)
    vehicle_capacities: list[VehicleCapacity] = field(default_factory=list)
    planning_strategy: PlanningStrategy = PlanningStrategy.MAX_UTILIZATION
    planning_trace: list[PlanningTraceEntry] = field(default_factory=list)
    planning_variants: list[PlanningVariant] = field(default_factory=list)
    estimated_capacity_minutes: int = 0
    estimated_demand_minutes: int = 0

    @property
    def assigned_count(self) -> int:
        return len(self.assignments)

    @property
    def open_count(self) -> int:
        return len(self.unassigned)

    @property
    def subcontractor_count(self) -> int:
        return sum(item.subcontractor_recommended for item in self.unassigned)

    @property
    def extended_tour_count(self) -> int:
        return sum(item.mode is AssignmentMode.EXTEND_TOUR for item in self.assignments)

    @property
    def new_tour_count(self) -> int:
        return sum(item.mode is AssignmentMode.NEW_TOUR for item in self.assignments)

    @property
    def average_score(self) -> float:
        if not self.assignments:
            return 0.0
        return sum(item.score for item in self.assignments) / len(self.assignments)

    @property
    def total_transfer_minutes(self) -> int:
        return sum(item.transfer_minutes for item in self.assignments)

    @property
    def total_waiting_minutes(self) -> int:
        return sum(item.waiting_minutes for item in self.assignments)

    @property
    def proposed_tour_count(self) -> int:
        return len(self.proposed_tours)

    @property
    def utilized_vehicle_count(self) -> int:
        return len({item.vehicle_id for item in self.assignments})

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions)

    @property
    def utilization_percent(self) -> float:
        if not self.resources_total:
            return 0.0
        return min(100.0, self.utilized_vehicle_count / self.resources_total * 100.0)
