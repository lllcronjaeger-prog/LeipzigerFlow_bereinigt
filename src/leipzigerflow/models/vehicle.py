from datetime import date
from enum import StrEnum

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class VehicleOwnership(StrEnum):
    OWN = "Eigenes Fahrzeug"
    FOREIGN = "Fremdfahrzeug"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class VehicleOperationType(StrEnum):
    LOCAL = "Nahverkehr"
    LONG_HAUL = "Fernverkehr"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class VehicleClass(StrEnum):
    STANDARD = "Standard"
    MEGA = "Mega"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class Vehicle(Base):
    """Zugmaschine des eigenen Fuhrparks."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_number: Mapped[str] = mapped_column(String(30), default="", nullable=False, index=True)
    license_plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vehicle_class: Mapped[str] = mapped_column(
        String(20), default=VehicleClass.STANDARD.value, nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    operation_type: Mapped[str] = mapped_column(
        String(20), default=VehicleOperationType.LOCAL.value, nullable=False, index=True
    )
    home_base: Mapped[str] = mapped_column(String(100), default="Ettlingen", nullable=False)
    home_base_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True, index=True
    )
    daily_return_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overnight_away_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ownership_type: Mapped[str] = mapped_column(
        String(30), default=VehicleOwnership.OWN.value, nullable=False, index=True
    )
    hu_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Frei", nullable=False, index=True)
    remarks: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trailer_id: Mapped[int | None] = mapped_column(ForeignKey("trailers.id"), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dispatch_group_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_groups.id"), nullable=True, index=True)

    # Legacy-Feld für bestehende Datenbanken.
    is_refrigerated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    trailer = relationship("Trailer", foreign_keys=[trailer_id])
    home_base_location = relationship("Location", foreign_keys=[home_base_location_id])
    dispatch_group = relationship("DispatchGroup", foreign_keys=[dispatch_group_id])
    dispatch_groups = relationship("DispatchGroup", secondary="dispatch_group_vehicles", back_populates="vehicles", lazy="selectin")
    absences = relationship(
        "VehicleAbsence",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        order_by="VehicleAbsence.starts_at",
    )
    tours = relationship("Tour", foreign_keys="Tour.vehicle_id", viewonly=True)
    resource_assignments = relationship(
        "VehicleResourceAssignment",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        order_by="VehicleResourceAssignment.valid_from",
        lazy="selectin",
    )
    staffing_profile = relationship(
        "VehicleStaffingProfile",
        back_populates="vehicle",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def is_mega(self) -> bool:
        return self.vehicle_class == VehicleClass.MEGA.value

    @property
    def display_name(self) -> str:
        return " – ".join(v for v in (self.vehicle_number, self.license_plate) if v)

    def __repr__(self) -> str:
        return f"Vehicle(id={self.id}, license_plate='{self.license_plate}')"
