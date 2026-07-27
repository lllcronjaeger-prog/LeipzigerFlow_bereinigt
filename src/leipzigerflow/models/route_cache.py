from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from leipzigerflow.database.base import Base


class RouteCacheEntry(Base):
    """Persisted route result for a normalized location pair and provider."""

    __tablename__ = "route_cache"
    __table_args__ = (
        UniqueConstraint(
            "origin_location_id",
            "destination_location_id",
            "provider",
            name="uq_route_cache_pair_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    origin_location_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    destination_location_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="osrm")
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    toll_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    countries: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class GeocodeCacheEntry(Base):
    """Coordinates resolved for one master-data location."""

    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    address_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="nominatim")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
