from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from leipzigerflow.database.base import Base


class Tour(Base):
    """Eine geplante Tour des eigenen Fuhrparks."""

    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(primary_key=True)

    tour_number: Mapped[str] = mapped_column(
        String(30, collation="NOCASE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tour_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    planned_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        default="Geplant",
        nullable=False,
        index=True,
    )

    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id"),
        nullable=True,
        index=True,
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id"),
        nullable=True,
        index=True,
    )

    trailer_id: Mapped[int | None] = mapped_column(
        ForeignKey("trailers.id"), nullable=True, index=True
    )

    planning_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    contractor_id: Mapped[int | None] = mapped_column(ForeignKey("contractors.id"), nullable=True, index=True)
    dispatch_group_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_groups.id"), nullable=True, index=True)
    planning_status: Mapped[str] = mapped_column(String(30), default="Geplant", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    tour_color: Mapped[str] = mapped_column(String(20), default="", nullable=False)

    remarks: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    driver = relationship("Driver")
    vehicle = relationship("Vehicle")
    trailer = relationship("Trailer")
    contractor = relationship("Contractor", back_populates="tours")
    dispatch_group = relationship("DispatchGroup", back_populates="tours")
    driver_assignments = relationship(
        "TourDriverAssignment",
        back_populates="tour",
        cascade="all, delete-orphan",
        order_by="TourDriverAssignment.sequence",
        lazy="selectin",
    )

    positions = relationship(
        "TourPosition",
        back_populates="tour",
        cascade="all, delete-orphan",
        order_by="TourPosition.position",
    )

    @property
    def driver_display(self) -> str:
        if not self.driver:
            return ""

        first_name = getattr(
            self.driver,
            "first_name",
            "",
        )
        last_name = getattr(
            self.driver,
            "last_name",
            "",
        )
        display_name = getattr(
            self.driver,
            "display_name",
            "",
        )

        return (
            str(display_name).strip()
            or f"{first_name} {last_name}".strip()
        )

    @property
    def vehicle_display(self) -> str:
        if not self.vehicle:
            return ""

        license_plate = getattr(
            self.vehicle,
            "license_plate",
            "",
        )
        description = getattr(
            self.vehicle,
            "description",
            "",
        )

        if license_plate and description:
            return f"{license_plate} – {description}"
        return str(license_plate or description)

    @property
    def trailer_display(self) -> str:
        if not self.trailer:
            return ""
        return getattr(self.trailer, "display_name", "") or getattr(self.trailer, "license_plate", "")

    @property
    def order_count(self) -> int:
        return len(self.positions)

    @property
    def search_text(self) -> str:
        values = [
            self.tour_number,
            self.status,
            self.driver_display,
            self.vehicle_display,
            self.trailer_display,
            self.remarks,
        ]
        return " ".join(
            str(value).lower()
            for value in values
            if value
        )

    def __repr__(self) -> str:
        return (
            "Tour("
            f"id={self.id}, "
            f"tour_number='{self.tour_number}'"
            ")"
        )
