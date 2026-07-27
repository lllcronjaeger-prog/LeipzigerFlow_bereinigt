from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from leipzigerflow.telematics.models import MovementState, VehiclePosition
from leipzigerflow.telematics.provider import (
    TelematicsNotConfiguredError,
    TelematicsProvider,
    TelematicsProviderError,
)


@dataclass(frozen=True, slots=True)
class SpedionConfig:
    """Konfiguration für die spätere produktive Spedion-Anbindung.

    Die konkreten Endpunkte und Feldnamen werden eingetragen, sobald die für den
    Betrieb freigeschaltete Spedion-Schnittstellendokumentation und Zugangsdaten
    vorliegen.
    """

    base_url: str = ""
    customer_id: str = ""
    api_key: str = ""
    timeout_seconds: int = 20

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url.strip() and self.api_key.strip())


class SpedionProvider(TelematicsProvider):
    """Spedion-Adapter mit injizierbarem Transport.

    Der Provider enthält absichtlich noch keinen fest verdrahteten HTTP-Aufruf.
    So bleibt kein möglicherweise falscher oder kundenspezifischer API-Endpunkt im
    Programm. Für Tests und die spätere produktive Anbindung wird eine Fetch-Funktion
    injiziert, die Listen von Spedion-Datensätzen zurückgibt.
    """

    def __init__(
        self,
        config: SpedionConfig,
        fetch_payload: Callable[[SpedionConfig, datetime | None], Iterable[Mapping[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self._fetch_payload = fetch_payload

    @property
    def provider_name(self) -> str:
        return "Spedion"

    def fetch_positions(self, since: datetime | None = None) -> list[VehiclePosition]:
        if not self.config.is_configured or self._fetch_payload is None:
            raise TelematicsNotConfiguredError(
                "Spedion ist noch nicht konfiguriert. API-Zugangsdaten und der "
                "freigegebene Schnittstellenendpunkt fehlen."
            )
        try:
            payload = self._fetch_payload(self.config, since)
            return [self._map_position(item) for item in payload]
        except TelematicsProviderError:
            raise
        except Exception as error:
            raise TelematicsProviderError(f"Spedion-Daten konnten nicht geladen werden: {error}") from error

    @staticmethod
    def _map_position(item: Mapping[str, Any]) -> VehiclePosition:
        latitude = SpedionProvider._float_value(item, "latitude", "lat", "gpsLatitude")
        longitude = SpedionProvider._float_value(item, "longitude", "lon", "lng", "gpsLongitude")
        speed = SpedionProvider._float_value(item, "speed_kmh", "speed", "velocity", default=0.0)
        recorded_at = SpedionProvider._datetime_value(
            item.get("recorded_at") or item.get("timestamp") or item.get("positionTime")
        )
        plate = str(
            item.get("license_plate")
            or item.get("licensePlate")
            or item.get("vehicleRegistration")
            or ""
        ).strip()
        external_id = str(item.get("vehicle_id") or item.get("vehicleId") or plate).strip()
        if not external_id or not plate:
            raise TelematicsProviderError("Ein Spedion-Datensatz enthält keine Fahrzeugkennung.")
        return VehiclePosition(
            external_vehicle_id=external_id,
            license_plate=plate,
            latitude=latitude,
            longitude=longitude,
            recorded_at=recorded_at,
            speed_kmh=max(0.0, speed),
            heading_degrees=SpedionProvider._optional_float(item.get("heading") or item.get("course")),
            movement_state=SpedionProvider._movement_state(item, speed),
            driver_name=str(item.get("driver_name") or item.get("driverName") or "").strip(),
            odometer_km=SpedionProvider._optional_float(item.get("odometer_km") or item.get("odometer")),
            raw_data=dict(item),
        )

    @staticmethod
    def _movement_state(item: Mapping[str, Any], speed: float) -> MovementState:
        raw = str(item.get("movement_state") or item.get("movementState") or "").strip().casefold()
        if raw in {"moving", "fahrt", "driving", "1", "true"} or speed >= 3.0:
            return MovementState.MOVING
        if raw in {"idling", "leerlauf"}:
            return MovementState.IDLING
        if raw in {"parked", "stand", "stopped", "0", "false"} or speed == 0:
            return MovementState.PARKED
        return MovementState.UNKNOWN

    @staticmethod
    def _float_value(item: Mapping[str, Any], *keys: str, default: float | None = None) -> float:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                try:
                    return float(str(value).replace(",", "."))
                except ValueError as error:
                    raise TelematicsProviderError(f"Ungültiger Zahlenwert für {key}: {value}") from error
        if default is not None:
            return default
        raise TelematicsProviderError(f"Pflichtwert fehlt: {'/'.join(keys)}")

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _datetime_value(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str) and value.strip():
            normalized = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError as error:
                raise TelematicsProviderError(f"Ungültiger Zeitstempel: {value}") from error
        return datetime.now(tz=timezone.utc)
