from datetime import date, time
from types import SimpleNamespace

from leipzigerflow.planner.driving_rules import DrivingRulesEngine
from leipzigerflow.planner.optimizer.route_provider import MatrixRouteProvider
from leipzigerflow.planner.quality import TourQualityEngine, TourQualityLevel
from leipzigerflow.planner.time_planning import TimePlanningEngine


def _tour(order_count: int, distance_km: float = 65.0):
    positions = []
    location_id = 1
    matrix = {}
    for index in range(order_count):
        loading = SimpleNamespace(
            id=location_id,
            name=f"Laden {index+1}",
            opening_hours="",
            loading_duration_minutes=60,
            unloading_duration_minutes=60,
        )
        unloading = SimpleNamespace(
            id=location_id + 1,
            name=f"Entladen {index+1}",
            opening_hours="",
            loading_duration_minutes=60,
            unloading_duration_minutes=60,
        )
        matrix[(loading.id, unloading.id)] = (distance_km, 1)
        if index:
            previous_unloading_id = location_id - 1
            matrix[(previous_unloading_id, loading.id)] = (distance_km, 1)
        order = SimpleNamespace(
            id=index + 1,
            order_number=f"A-{index+1}",
            loading_location=loading,
            unloading_location=unloading,
            loading_date=date(2026, 7, 21),
            unloading_date=date(2026, 7, 21),
            loading_time_from=None,
            loading_time_until=None,
            unloading_time_from=None,
            unloading_time_until=None,
        )
        positions.append(SimpleNamespace(id=index + 1, position=index + 1, transport_order=order))
        location_id += 2
    tour = SimpleNamespace(
        id=1,
        tour_date=date(2026, 7, 21),
        planned_start_time=time(6, 0),
        positions=positions,
        driver=None,
    )
    return tour, MatrixRouteProvider(matrix)


def test_driving_time_is_derived_from_distance_at_65_kmh():
    tour, provider = _tour(2, distance_km=65.0)
    engine = TimePlanningEngine(provider, average_speed_kmh=65)
    schedule = engine.build_schedule(tour)
    assessment = DrivingRulesEngine(engine).evaluate(tour, schedule)
    assert assessment.estimated_driving_minutes == 180  # 3 legs x 60 minutes
    assert assessment.estimated_shift_minutes == 450  # 4 services + 3 hours driving + 30 Min. Arbeitszeitpause


def test_break_is_inserted_after_four_and_half_hours():
    tour, provider = _tour(3, distance_km=65.0)
    engine = TimePlanningEngine(provider, average_speed_kmh=65)
    schedule = engine.build_schedule(tour)
    assessment = DrivingRulesEngine(engine).evaluate(tour, schedule)
    assert assessment.required_break_minutes == 75
    assert len(schedule.breaks) == 2
    driving_break = next(item for item in schedule.breaks if "4:30 h Lenkzeit" in item.reason)
    assert driving_break.started_at == schedule.start_at.replace(hour=16, minute=0)
    assert any(issue.code == "driving_break_planned" for issue in assessment.issues)


def test_osm_duration_is_not_used_when_distance_is_available():
    tour, _ = _tour(1)
    loading = tour.positions[0].transport_order.loading_location
    unloading = tour.positions[0].transport_order.unloading_location
    provider = MatrixRouteProvider({(loading.id, unloading.id): (130.0, 15)})
    schedule = TimePlanningEngine(provider, average_speed_kmh=65).build_schedule(tour)
    assert schedule.total_driving_minutes == 120
    assert schedule.stops[1].planned_arrival.hour == 9


def test_quality_turns_red_for_error():
    issue = SimpleNamespace(severity="error")
    quality = TourQualityEngine().evaluate(driving_issues=[issue])
    assert quality.level == TourQualityLevel.RED
    assert quality.score < 100


def test_working_time_break_is_inserted_after_six_hours_without_driving_break():
    tour, provider = _tour(2, distance_km=65.0)
    schedule = TimePlanningEngine(provider, average_speed_kmh=65).build_schedule(tour)
    working_breaks = [item for item in schedule.breaks if "Arbeitszeitpause" in item.reason]
    assert len(working_breaks) == 1
    assert working_breaks[0].minutes == 30
    assert working_breaks[0].started_at == schedule.start_at.replace(hour=12, minute=0)


def test_earlier_driving_break_also_satisfies_working_time_break():
    tour, provider = _tour(1, distance_km=325.0)  # 5 Stunden Fahrt bei 65 km/h
    schedule = TimePlanningEngine(provider, average_speed_kmh=65).build_schedule(tour)
    assert len(schedule.breaks) == 1
    assert schedule.breaks[0].minutes == 45
    assert "4:30 h Lenkzeit" in schedule.breaks[0].reason
    assert not any("spätestens 6 Stunden" in item.reason for item in schedule.breaks)


def test_next_day_delivery_creates_daily_rest_and_separate_duty_days():
    tour, provider = _tour(1, distance_km=130.0)
    order = tour.positions[0].transport_order
    order.unloading_date = date(2026, 7, 22)
    order.unloading_time_from = time(7, 0)
    order.unloading_time_until = time(9, 0)
    schedule = TimePlanningEngine(provider, average_speed_kmh=65).build_schedule(tour)
    assessment = DrivingRulesEngine().evaluate(tour, schedule)
    assert len(schedule.duty_days) == 2
    assert any(item.is_daily_rest for item in schedule.breaks)
    assert not any(issue.code == "shift_too_long" for issue in assessment.issues)
    assert assessment.estimated_shift_minutes <= 15 * 60


def test_long_leg_is_split_at_daily_limit_and_continued_after_rest():
    tour, provider = _tour(1, distance_km=780.0)  # 12 Stunden reine Fahrzeit
    order = tour.positions[0].transport_order
    order.unloading_date = date(2026, 7, 22)
    schedule = TimePlanningEngine(provider, average_speed_kmh=65).build_schedule(tour)
    assert len(schedule.duty_days) == 2
    assert any(travel.partial for travel in schedule.travels)
    assert any("Zwischenstopp Richtung" in travel.destination_name for travel in schedule.travels)
    assert schedule.duty_days[0].driving_minutes <= 9 * 60
