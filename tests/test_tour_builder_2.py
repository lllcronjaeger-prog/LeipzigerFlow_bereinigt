from datetime import datetime, timedelta

from leipzigerflow.planner.engine.models import AssignmentMode, ProposedAssignment
from leipzigerflow.planner.engine.tour_builder import AutomaticTourBuilder


def assignment(number, start, loading, unloading, trailer="Plane"):
    return ProposedAssignment(
        vehicle_id=1, vehicle_label="L-101", driver_id=2, driver_label="Müller",
        order_id=int(number), order_number=number, score=80, loading_at=start,
        available_again_at=start + timedelta(hours=2), mode=AssignmentMode.NEW_TOUR,
        loading_location_label=loading, unloading_location_label=unloading,
        required_trailer_types=trailer,
    )


def test_builder_clusters_same_region_and_trailer():
    start = datetime(2026, 7, 22, 6)
    tours = AutomaticTourBuilder().build([
        assignment("1", start, "04103 Leipzig", "06108 Halle"),
        assignment("2", start + timedelta(hours=3), "06108 Halle", "06217 Merseburg"),
    ])
    assert len(tours) == 1
    assert tours[0].order_count == 2
    assert tours[0].cluster_score >= 80
    assert "Region 06" in tours[0].cluster_label


def test_builder_splits_incompatible_trailer_and_region():
    start = datetime(2026, 7, 22, 6)
    tours = AutomaticTourBuilder().build([
        assignment("1", start, "04103 Leipzig", "06108 Halle", "Plane"),
        assignment("2", start + timedelta(hours=3), "20095 Hamburg", "28195 Bremen", "Kühler"),
    ])
    assert len(tours) == 2
    assert all(tour.order_count == 1 for tour in tours)
