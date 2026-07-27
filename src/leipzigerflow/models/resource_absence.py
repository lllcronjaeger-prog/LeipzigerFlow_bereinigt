from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class AbsenceReason(StrEnum):
    WORKSHOP = "Werkstatt"
    MAINTENANCE = "Wartung"
    INSPECTION = "TÜV / Prüfung"
    REPAIR = "Reparatur"
    RENTED = "Vermietung"
    OUT_OF_SERVICE = "Außer Betrieb"
    OTHER = "Sonstige Sperre"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class VehicleAbsence(Base):
    __tablename__ = "vehicle_absences"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False, default=AbsenceReason.WORKSHOP.value)
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    vehicle = relationship("Vehicle", back_populates="absences")

    def overlaps(self, starts_at: datetime, ends_at: datetime) -> bool:
        return self.active and self.starts_at < ends_at and starts_at < self.ends_at


class TrailerAbsence(Base):
    __tablename__ = "trailer_absences"

    id: Mapped[int] = mapped_column(primary_key=True)
    trailer_id: Mapped[int] = mapped_column(ForeignKey("trailers.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False, default=AbsenceReason.WORKSHOP.value)
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    trailer = relationship("Trailer", back_populates="absences")

    def overlaps(self, starts_at: datetime, ends_at: datetime) -> bool:
        return self.active and self.starts_at < ends_at and starts_at < self.ends_at
