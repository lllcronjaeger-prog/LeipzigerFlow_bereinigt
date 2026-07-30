from enum import StrEnum

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class ContractorType(StrEnum):
    OWN_FLEET = "Eigener Fuhrpark"
    SUBCONTRACTOR = "Subunternehmer"


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_code: Mapped[str] = mapped_column(String(100, collation="NOCASE"), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    contractor_type: Mapped[str] = mapped_column(String(30), default=ContractorType.SUBCONTRACTOR.value, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    contact_person: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    remarks: Mapped[str] = mapped_column(Text, default="", nullable=False)

    orders = relationship("TransportOrder", back_populates="contractor")
    tours = relationship("Tour", back_populates="contractor")
    dispatch_groups = relationship("DispatchGroup", secondary="dispatch_group_contractors", back_populates="contractors", lazy="selectin")

    @property
    def is_own_fleet(self) -> bool:
        return self.contractor_type == ContractorType.OWN_FLEET.value

    @property
    def display_name(self) -> str:
        return f"{self.match_code} | {self.name}" if self.name else self.match_code
