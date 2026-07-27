from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leipzigerflow.database.base import Base
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.routing import Coordinates, RouteResult, RoutingService


class FakeGeocoder:
    name = "fake-geocoder"

    def __init__(self):
        self.calls = 0

    def geocode(self, address: str):
        self.calls += 1
        if "Leipzig" in address:
            return Coordinates(51.3397, 12.3731)
        if "Halle" in address:
            return Coordinates(51.4825, 11.9705)
        return None


class FakeRouter:
    name = "fake-router"

    def __init__(self):
        self.calls = 0

    def calculate(self, origin: Coordinates, destination: Coordinates):
        self.calls += 1
        return RouteResult(42.5, 38, provider=self.name)


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([
            Location(
                location_type=LocationType.DEPOT,
                name="Werk Leipzig",
                street="Werkstraße",
                house_number="1",
                postal_code="04249",
                city="Leipzig",
                country="Deutschland",
            ),
            Location(
                location_type=LocationType.CUSTOMER,
                name="Lager Halle",
                street="Industriestraße",
                house_number="2",
                postal_code="06112",
                city="Halle",
                country="Deutschland",
            ),
        ])
        session.commit()
    return factory


def test_routing_result_is_persistently_cached():
    factory = _session_factory()
    geocoder = FakeGeocoder()
    router = FakeRouter()
    service = RoutingService(
        session_factory=factory,
        geocoder=geocoder,
        provider=router,
        enabled=True,
    )

    first = service.calculate(1, 2)
    second = service.calculate(1, 2)

    assert first.distance_km == 42.5
    assert first.duration_minutes == 38
    assert first.from_cache is False
    assert second.from_cache is True
    assert router.calls == 1
    assert geocoder.calls == 2


def test_address_change_invalidates_geocode_by_fingerprint():
    factory = _session_factory()
    geocoder = FakeGeocoder()
    router = FakeRouter()
    service = RoutingService(session_factory=factory, geocoder=geocoder, provider=router)

    service.calculate(1, 2)
    service.invalidate_location(1)
    with factory() as session:
        location = session.get(Location, 1)
        location.house_number = "99"
        session.commit()

    result = service.calculate(1, 2)

    assert result.estimated is False
    assert geocoder.calls == 3
    assert router.calls == 2


def test_network_failure_returns_marked_conservative_fallback():
    class BrokenRouter:
        name = "broken"

        def calculate(self, origin, destination):
            raise TimeoutError("Zeitüberschreitung")

    service = RoutingService(
        session_factory=_session_factory(),
        geocoder=FakeGeocoder(),
        provider=BrokenRouter(),
        default_duration_minutes=75,
    )

    result = service.calculate(1, 2)

    assert result.distance_km is not None
    assert result.distance_km > 0
    assert result.duration_minutes == 75
    assert result.estimated is True
    assert "Zeitüberschreitung" in result.warning


def test_disabled_routing_does_not_call_network():
    geocoder = FakeGeocoder()
    router = FakeRouter()
    service = RoutingService(
        session_factory=_session_factory(),
        geocoder=geocoder,
        provider=router,
        enabled=False,
    )

    result = service.calculate(1, 2)

    assert result.estimated is True
    assert geocoder.calls == 0
    assert router.calls == 0


def test_route_protocol_returns_optimizer_leg():
    service = RoutingService(
        session_factory=_session_factory(),
        geocoder=FakeGeocoder(),
        provider=FakeRouter(),
    )

    leg = service.route(1, 2)

    assert leg.distance_km == 42.5
    assert leg.duration_minutes == 38
    assert leg.estimated is False
