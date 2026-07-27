from datetime import datetime, timezone

import pytest

from leipzigerflow.telematics import (
    MovementState,
    SpedionConfig,
    SpedionProvider,
    TelematicsEventEngine,
    TelematicsEventType,
    TelematicsNotConfiguredError,
    VehiclePosition,
)


def test_spedion_provider_requires_configuration():
    provider = SpedionProvider(SpedionConfig())
    with pytest.raises(TelematicsNotConfiguredError):
        provider.fetch_positions()


def test_spedion_payload_is_mapped():
    config = SpedionConfig(base_url="https://example.invalid", api_key="secret")
    provider = SpedionProvider(
        config,
        fetch_payload=lambda _config, _since: [
            {
                "vehicleId": "4711",
                "licensePlate": "L-LF 100",
                "lat": "51.34",
                "lon": "12.37",
                "speed": "67",
                "timestamp": "2026-07-21T08:00:00+00:00",
            }
        ],
    )
    position = provider.fetch_positions()[0]
    assert position.license_plate == "L-LF 100"
    assert position.movement_state == MovementState.MOVING
    assert position.latitude == 51.34


def test_event_engine_detects_movement_start():
    engine = TelematicsEventEngine()
    first = VehiclePosition(
        external_vehicle_id="1",
        license_plate="L-LF 100",
        latitude=51.0,
        longitude=12.0,
        recorded_at=datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc),
        movement_state=MovementState.PARKED,
    )
    second = VehiclePosition(
        external_vehicle_id="1",
        license_plate="L-LF 100",
        latitude=51.1,
        longitude=12.1,
        recorded_at=datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc),
        speed_kmh=50,
        movement_state=MovementState.MOVING,
    )
    engine.ingest([first])
    events = engine.ingest([second])
    assert any(event.event_type == TelematicsEventType.MOVEMENT_STARTED for event in events)
