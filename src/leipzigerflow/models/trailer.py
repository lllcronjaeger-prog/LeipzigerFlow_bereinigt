from __future__ import annotations

from datetime import date
from enum import StrEnum

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class TrailerType(StrEnum):
    PLANE = "Plane"
    MEGA_PLANE = "Mega-Plane"
    BOX = "Koffer"
    MEGA_BOX = "Mega-Koffer"
    REFRIGERATED = "Kühler"
    MEGA_REFRIGERATED = "Mega-Kühler"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class Trailer(Base):
    __tablename__ = "trailers"

    id: Mapped[int] = mapped_column(primary_key=True)
    trailer_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    license_plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    trailer_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    hu_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Frei", nullable=False, index=True)
    remarks: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    absences = relationship(
        "TrailerAbsence",
        back_populates="trailer",
        cascade="all, delete-orphan",
        order_by="TrailerAbsence.starts_at",
    )
    tours = relationship("Tour", foreign_keys="Tour.trailer_id", viewonly=True)
    dispatch_groups = relationship("DispatchGroup", secondary="dispatch_group_trailers", back_populates="trailers", lazy="selectin")

    @property
    def is_mega(self) -> bool:
        return self.trailer_type in {TrailerType.MEGA_PLANE, TrailerType.MEGA_BOX, TrailerType.MEGA_REFRIGERATED}

    @property
    def is_refrigerated(self) -> bool:
        return self.trailer_type in {TrailerType.REFRIGERATED, TrailerType.MEGA_REFRIGERATED}

    @property
    def display_name(self) -> str:
        return f"{self.trailer_number} – {self.license_plate} – {self.trailer_type}"
