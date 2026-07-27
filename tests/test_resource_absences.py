from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from leipzigerflow.models.resource_absence import VehicleAbsence, TrailerAbsence
from leipzigerflow.planner.warnings import TourWarningEngine, WarningSeverity


class FakeTimeEngine:
    def build_schedule(self, tour):
        return SimpleNamespace(start_at=tour.start_at, end_at=tour.end_at)


def _tour():
    start = datetime(2026, 7, 24, 8, 0)
    vehicle = SimpleNamespace(active=True, hu_date=date(2027, 1, 1), absences=[], tours=[], is_mega=False, trailer=None)
    trailer = SimpleNamespace(active=True, hu_date=date(2027, 1, 1), sp_date=date(2027, 1, 1), absences=[], tours=[], is_mega=False, trailer_type="Plane")
    tour = SimpleNamespace(id=1, tour_number="T-1", tour_date=start.date(), start_at=start, end_at=start + timedelta(hours=8),
        driver=SimpleNamespace(active=True, license_valid_until=date(2027, 1, 1)), vehicle=vehicle, trailer=trailer, positions=[])
    vehicle.tours=[tour]; trailer.tours=[tour]
    return tour


def test_vehicle_absence_overlapping_tour_is_error():
    tour = _tour()
    tour.vehicle.absences = [SimpleNamespace(active=True, starts_at=tour.start_at + timedelta(hours=1), ends_at=tour.end_at + timedelta(hours=1), reason="Werkstatt", remarks="Bremsen")]
    warnings = TourWarningEngine(FakeTimeEngine()).evaluate(tour)
    item = next(w for w in warnings if w.code == "vehicle_absence")
    assert item.severity == WarningSeverity.ERROR
    assert "Werkstatt" in item.message


def test_absence_ending_at_tour_start_does_not_overlap():
    tour = _tour()
    tour.trailer.absences = [SimpleNamespace(active=True, starts_at=tour.start_at - timedelta(days=1), ends_at=tour.start_at, reason="Wartung", remarks="")]
    warnings = TourWarningEngine(FakeTimeEngine()).evaluate(tour)
    assert not any(w.code == "trailer_absence" for w in warnings)


def test_standard_vehicle_with_mega_trailer_is_error():
    tour = _tour(); tour.trailer.is_mega = True; tour.trailer.trailer_type = "Mega-Plane"
    warnings = TourWarningEngine(FakeTimeEngine()).evaluate(tour)
    assert any(w.code == "vehicle_trailer_incompatible" and w.severity == WarningSeverity.ERROR for w in warnings)
