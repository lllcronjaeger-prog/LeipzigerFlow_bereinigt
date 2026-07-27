from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from leipzigerflow.config.settings import (
    ROUTING_CACHE_DAYS,
    ROUTING_DEFAULT_DURATION_MINUTES,
    ROUTING_ENABLED,
    ROUTING_GEOCODER_URL,
    ROUTING_OSRM_URL,
    ROUTING_FALLBACK_SPEED_KMH,
)
from leipzigerflow.database.session import SessionLocal
from leipzigerflow.models.location import Location
from leipzigerflow.models.route_cache import GeocodeCacheEntry, RouteCacheEntry
from leipzigerflow.planner.optimizer.route_provider import RouteLeg
from leipzigerflow.routing.models import Coordinates, RouteResult
from leipzigerflow.routing.providers import NominatimGeocodingProvider, OsrmRoutingProvider

LOGGER = logging.getLogger(__name__)


class RoutingService:
    """Central, provider-independent routing engine with persistent caching.

    The service implements the optimizer's ``RouteProvider`` protocol through
    ``route(location_id, location_id)``. Network failures never make planning
    unusable: a conservative estimated leg is returned and is clearly marked.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        geocoder=None,
        provider=None,
        enabled: bool = ROUTING_ENABLED,
        cache_days: int = ROUTING_CACHE_DAYS,
        default_duration_minutes: int = ROUTING_DEFAULT_DURATION_MINUTES,
        fallback_speed_kmh: float = ROUTING_FALLBACK_SPEED_KMH,
    ) -> None:
        self.session_factory = session_factory
        self.geocoder = geocoder or NominatimGeocodingProvider(base_url=ROUTING_GEOCODER_URL)
        self.provider = provider or OsrmRoutingProvider(base_url=ROUTING_OSRM_URL)
        self.enabled = bool(enabled)
        self.cache_days = max(1, int(cache_days))
        self.default_duration_minutes = max(0, int(default_duration_minutes))
        self.fallback_speed_kmh = max(1.0, float(fallback_speed_kmh))

    def route(self, origin_location_id: int, destination_location_id: int) -> RouteLeg:
        result = self.calculate(origin_location_id, destination_location_id)
        return RouteLeg(result.distance_km, result.duration_minutes, estimated=result.estimated)

    def calculate(self, origin_location_id: int, destination_location_id: int) -> RouteResult:
        if origin_location_id == destination_location_id:
            return RouteResult(0.0, 0, provider="local", from_cache=True)

        with self.session_factory() as session:
            cached = self._get_route_cache(session, origin_location_id, destination_location_id)
            if cached is not None:
                return cached

            if not self.enabled:
                return self._fallback("Online-Routing ist deaktiviert.")

            origin = session.get(Location, origin_location_id)
            destination = session.get(Location, destination_location_id)
            if origin is None or destination is None:
                return self._fallback("Start- oder Zielort wurde nicht gefunden.")

            try:
                origin_coordinates = self._coordinates(session, origin)
                destination_coordinates = self._coordinates(session, destination)
                if origin_coordinates is None or destination_coordinates is None:
                    return self._fallback("Adresse konnte nicht eindeutig geocodiert werden.")
                result = self.provider.calculate(origin_coordinates, destination_coordinates)
                self._store_route(session, origin.id, destination.id, result)
                session.commit()
                return result
            except Exception as error:  # routing must not abort the disposition
                session.rollback()
                LOGGER.warning("Routing fehlgeschlagen: %s", error)
                return self._fallback(f"Routingdienst nicht erreichbar: {error}")

    def warm_up(self, pairs: list[tuple[int, int]]) -> dict[str, int]:
        """Calculates uncached route pairs, useful before a planning run."""
        calculated = cached = estimated = 0
        for origin, destination in dict.fromkeys(pairs):
            result = self.calculate(origin, destination)
            if result.from_cache:
                cached += 1
            elif result.estimated:
                estimated += 1
            else:
                calculated += 1
        return {"calculated": calculated, "cached": cached, "estimated": estimated}

    def invalidate_location(self, location_id: int) -> None:
        """Removes routes/geocodes after an address in master data changed."""
        with self.session_factory() as session:
            session.query(RouteCacheEntry).filter(
                (RouteCacheEntry.origin_location_id == location_id)
                | (RouteCacheEntry.destination_location_id == location_id)
            ).delete(synchronize_session=False)
            session.query(GeocodeCacheEntry).filter(
                GeocodeCacheEntry.location_id == location_id
            ).delete(synchronize_session=False)
            session.commit()

    def _get_route_cache(self, session: Session, origin_id: int, destination_id: int) -> RouteResult | None:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=self.cache_days)
        provider_name = getattr(self.provider, "name", "routing")
        entry = session.scalar(
            select(RouteCacheEntry).where(
                RouteCacheEntry.origin_location_id == origin_id,
                RouteCacheEntry.destination_location_id == destination_id,
                RouteCacheEntry.provider == provider_name,
                RouteCacheEntry.calculated_at >= cutoff,
            )
        )
        if entry is None:
            return None
        return RouteResult(
            distance_km=entry.distance_km,
            duration_minutes=entry.duration_minutes,
            toll_km=entry.toll_km,
            countries=tuple(part for part in entry.countries.split(";") if part),
            provider=entry.provider,
            from_cache=True,
            estimated=False,
        )

    def _coordinates(self, session: Session, location: Location) -> Coordinates | None:
        address = location.full_address.replace("\n", ", ").strip()
        fingerprint = hashlib.sha256(address.casefold().encode("utf-8")).hexdigest()
        cached = session.scalar(
            select(GeocodeCacheEntry).where(
                GeocodeCacheEntry.location_id == location.id,
                GeocodeCacheEntry.address_fingerprint == fingerprint,
            )
        )
        if cached is not None:
            return Coordinates(cached.latitude, cached.longitude)

        # Vollständige Straßenadresse zuerst; bei uneindeutigen oder noch unvollständig
        # gepflegten Standorten schrittweise auf PLZ/Ort zurückfallen. Dadurch kann das
        # Entfernungswerk auch dann eine Strecke liefern, wenn Hausnummer oder Straße
        # vom Geocoder nicht erkannt werden.
        candidates = [
            address,
            ", ".join(part for part in [f"{location.postal_code} {location.city}".strip(), location.country] if part),
            ", ".join(part for part in [location.postal_code, location.country] if part),
            ", ".join(part for part in [location.city, location.country] if part),
        ]
        coordinates = None
        for candidate in dict.fromkeys(item.strip() for item in candidates if item and item.strip()):
            coordinates = self.geocoder.geocode(candidate)
            if coordinates is not None:
                break
        if coordinates is None:
            return None
        old = session.scalar(
            select(GeocodeCacheEntry).where(GeocodeCacheEntry.location_id == location.id)
        )
        if old is None:
            old = GeocodeCacheEntry(
                location_id=location.id,
                address_fingerprint=fingerprint,
                latitude=coordinates.latitude,
                longitude=coordinates.longitude,
                provider=getattr(self.geocoder, "name", "geocoder"),
                calculated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(old)
        else:
            old.address_fingerprint = fingerprint
            old.latitude = coordinates.latitude
            old.longitude = coordinates.longitude
            old.provider = getattr(self.geocoder, "name", "geocoder")
            old.calculated_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return coordinates

    def _store_route(self, session: Session, origin_id: int, destination_id: int, result: RouteResult) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        provider_name = getattr(self.provider, "name", result.provider)
        entry = session.scalar(
            select(RouteCacheEntry).where(
                RouteCacheEntry.origin_location_id == origin_id,
                RouteCacheEntry.destination_location_id == destination_id,
                RouteCacheEntry.provider == provider_name,
            )
        )
        values = {
            "distance_km": float(result.distance_km or 0.0),
            "duration_minutes": int(result.duration_minutes),
            "toll_km": float(result.toll_km),
            "countries": ";".join(result.countries),
            "calculated_at": now,
        }
        if entry is None:
            session.add(RouteCacheEntry(
                origin_location_id=origin_id,
                destination_location_id=destination_id,
                provider=provider_name,
                **values,
            ))
        else:
            for name, value in values.items():
                setattr(entry, name, value)

    def _fallback(self, warning: str) -> RouteResult:
        # Auch bei einem vorübergehend nicht erreichbaren Routingdienst bleibt die
        # Entfernung sichtbar. Der Wert wird bewusst als Schätzung gekennzeichnet
        # und aus der konservativen Ersatzfahrzeit abgeleitet.
        estimated_distance = round(
            self.default_duration_minutes / 60.0 * self.fallback_speed_kmh, 1
        ) if self.default_duration_minutes else 0.0
        return RouteResult(
            distance_km=estimated_distance,
            duration_minutes=self.default_duration_minutes,
            provider="fallback",
            estimated=True,
            warning=warning,
        )


_default_service: RoutingService | None = None


def get_default_routing_service() -> RoutingService:
    global _default_service
    if _default_service is None:
        _default_service = RoutingService()
    return _default_service
