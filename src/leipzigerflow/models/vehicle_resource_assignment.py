from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class VehicleResourceAssignment(Base):
    """Zeitlich gültige Stammbesetzung eines Fahrzeugs.

    Die Zuordnung ist die Quelle für zukünftige Touren. Eine konkrete Tour kann
    weiterhin abweichende Fahrerabschnitte besitzen.
    """

    __tablename__ = "vehicle_resource_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    trailer_id: Mapped[int | None] = mapped_column(ForeignKey("trailers.id"), nullable=True, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    base_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    base_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    vehicle = relationship("Vehicle", back_populates="resource_assignments")
    driver = relationship("Driver")
    trailer = relationship("Trailer")
    base_location = relationship("Location")
