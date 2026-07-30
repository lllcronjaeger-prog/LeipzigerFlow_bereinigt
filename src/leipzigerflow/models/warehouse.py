from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class WarehouseGroup(Base):
    __tablename__ = "warehouse_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100, collation="NOCASE"), unique=True, nullable=False)
    aliases: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    monday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    tuesday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    wednesday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    thursday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    friday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    saturday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    sunday_hours: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    standard_loading_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    standard_unloading_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    standard_waiting_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    locations = relationship("Location", back_populates="warehouse_group")

    def hours_for_weekday(self, weekday: int) -> str:
        return (
            self.monday_hours, self.tuesday_hours, self.wednesday_hours,
            self.thursday_hours, self.friday_hours, self.saturday_hours,
            self.sunday_hours,
        )[weekday]
