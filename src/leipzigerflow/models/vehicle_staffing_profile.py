from datetime import time

from sqlalchemy import Boolean, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class VehicleStaffingProfile(Base):
    """Standardbesetzung einer Zugmaschine für die tägliche Touranlage.

    Die Zuordnung ist nur eine Vorlage. Die operative Fahrerzuordnung bleibt
    weiterhin an der konkreten Tour gespeichert.
    """

    __tablename__ = "vehicle_staffing_profiles"
    __table_args__ = (UniqueConstraint("vehicle_id", name="uq_vehicle_staffing_vehicle"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    relief_driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    sequential_double_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_shift_start: Mapped[time] = mapped_column(Time, default=time(6, 0), nullable=False)
    shift_minutes: Mapped[int] = mapped_column(Integer, default=10 * 60, nullable=False)

    vehicle = relationship("Vehicle", back_populates="staffing_profile")
    primary_driver = relationship("Driver", foreign_keys=[primary_driver_id])
    relief_driver = relationship("Driver", foreign_keys=[relief_driver_id])
