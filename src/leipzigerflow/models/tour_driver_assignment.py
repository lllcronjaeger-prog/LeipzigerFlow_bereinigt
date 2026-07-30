from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class TourDriverAssignment(Base):
    """Zeitlich eindeutiger Fahrerabschnitt innerhalb genau einer Tour."""

    __tablename__ = "tour_driver_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    change_base_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    change_base_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    change_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    tour = relationship("Tour", back_populates="driver_assignments")
    driver = relationship("Driver")
    change_base_location = relationship("Location")
