from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from leipzigerflow.database.base import Base

class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    street: Mapped[str] = mapped_column(String(150), default="")
    house_number: Mapped[str] = mapped_column(String(20), default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    country: Mapped[str] = mapped_column(String(100), default="Deutschland")
    phone: Mapped[str] = mapped_column(String(50), default="")
    mobile: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    contact_raw: Mapped[str] = mapped_column(String(500), default="")
    import_source: Mapped[str] = mapped_column(String(100), default="")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_number: Mapped[str] = mapped_column(String(100), default="")
    license_classes: Mapped[str] = mapped_column(String(100), default="")
    license_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    driver_card_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    module_95_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    adr_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_model: Mapped[str] = mapped_column(String(20), default="MO-FR")
    rotation_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    home_base: Mapped[str] = mapped_column(String(100), default="Ettlingen")
    home_base_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    allowed_operation: Mapped[str] = mapped_column(String(20), default="Beides")
    weekly_target_minutes: Mapped[int] = mapped_column(Integer, default=2880)
    double_week_limit_minutes: Mapped[int] = mapped_column(Integer, default=5760)
    absence_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    absence_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    absence_reason: Mapped[str] = mapped_column(String(100), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    dispatch_group_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_groups.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    home_base_location = relationship("Location", foreign_keys=[home_base_location_id])
    dispatch_group = relationship("DispatchGroup", foreign_keys=[dispatch_group_id])
    dispatch_groups = relationship("DispatchGroup", secondary="dispatch_group_drivers", back_populates="drivers", lazy="selectin")
    absences = relationship(
        "DriverAbsence",
        back_populates="driver",
        cascade="all, delete-orphan",
        order_by="DriverAbsence.starts_at",
    )
    @property
    def full_name(self): return f"{self.first_name} {self.last_name}".strip()
    @property
    def full_address(self):
        return ", ".join(p for p in (f"{self.street} {self.house_number}".strip(), f"{self.postal_code} {self.city}".strip(), self.country) if p)
    @property
    def search_text(self):
        return " ".join(str(v) for v in (self.match_code,self.full_name,self.city,self.phone,self.mobile,self.email,self.license_number,self.license_classes,self.absence_reason) if v).lower()
    def __repr__(self): return f"<Driver(id={self.id}, name={self.full_name!r})>"
