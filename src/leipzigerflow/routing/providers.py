from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from leipzigerflow.routing.models import Coordinates, RouteResult


class GeocodingProvider(Protocol):
    name: str

    def geocode(self, address: str) -> Coordinates | None:
        ...


class RoutingProvider(Protocol):
    name: str

    def calculate(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        ...


JsonLoader = Callable[[str, dict[str, str], float], object]


def _load_json(url: str, headers: dict[str, str], timeout: float) -> object:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is configured by the application
        return json.loads(response.read().decode("utf-8"))


@dataclass(slots=True)
class NominatimGeocodingProvider:
    base_url: str = "https://nominatim.openstreetmap.org/search"
    user_agent: str = "LeipzigerFlow/2026.16.1.1"
    timeout_seconds: float = 8.0
    json_loader: JsonLoader = _load_json
    name: str = "nominatim"

    def geocode(self, address: str) -> Coordinates | None:
        if not address.strip():
            return None
        query = urlencode({"q": address, "format": "jsonv2", "limit": 1})
        payload = self.json_loader(
            f"{self.base_url}?{query}",
            {"User-Agent": self.user_agent, "Accept": "application/json"},
            self.timeout_seconds,
        )
        if not isinstance(payload, list) or not payload:
            return None
        item = payload[0]
        if not isinstance(item, dict):
            return None
        try:
            return Coordinates(latitude=float(item["lat"]), longitude=float(item["lon"]))
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(slots=True)
class OsrmRoutingProvider:
    base_url: str = "https://router.project-osrm.org"
    profile: str = "driving"
    timeout_seconds: float = 10.0
    json_loader: JsonLoader = _load_json
    name: str = "osrm"

    def calculate(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        coordinates = (
            f"{origin.longitude:.7f},{origin.latitude:.7f};"
            f"{destination.longitude:.7f},{destination.latitude:.7f}"
        )
        url = f"{self.base_url.rstrip('/')}/route/v1/{self.profile}/{coordinates}?overview=false&steps=false"
        payload = self.json_loader(url, {"Accept": "application/json"}, self.timeout_seconds)
        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            raise RuntimeError("OSRM konnte keine Route berechnen.")
        routes = payload.get("routes")
        if not isinstance(routes, list) or not routes:
            raise RuntimeError("OSRM lieferte keine Route.")
        route = routes[0]
        if not isinstance(route, dict):
            raise RuntimeError("OSRM-Antwort ist ungültig.")
        distance_km = round(float(route["distance"]) / 1000.0, 1)
        duration_minutes = max(1, round(float(route["duration"]) / 60.0))
        return RouteResult(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            provider=self.name,
            estimated=False,
        )
