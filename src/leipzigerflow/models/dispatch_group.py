from sqlalchemy import Boolean, ForeignKey, Integer, String, Table, Column, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


def _link_table(name: str, target_table: str, target_column: str):
    return Table(
        name, Base.metadata,
        Column("dispatch_group_id", ForeignKey("dispatch_groups.id", ondelete="CASCADE"), primary_key=True),
        Column(target_column, ForeignKey(f"{target_table}.id", ondelete="CASCADE"), primary_key=True),
    )


dispatch_group_users = _link_table("dispatch_group_users", "users", "user_id")
dispatch_group_vehicles = _link_table("dispatch_group_vehicles", "vehicles", "vehicle_id")
dispatch_group_trailers = _link_table("dispatch_group_trailers", "trailers", "trailer_id")
dispatch_group_drivers = _link_table("dispatch_group_drivers", "drivers", "driver_id")
dispatch_group_contractors = _link_table("dispatch_group_contractors", "contractors", "contractor_id")


class DispatchGroup(Base):
    __tablename__ = "dispatch_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100, collation="NOCASE"), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#4472C4", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_contractor_id: Mapped[int | None] = mapped_column(ForeignKey("contractors.id"), nullable=True)

    vehicles = relationship("Vehicle", secondary=dispatch_group_vehicles, back_populates="dispatch_groups", lazy="selectin")
    trailers = relationship("Trailer", secondary=dispatch_group_trailers, back_populates="dispatch_groups", lazy="selectin")
    drivers = relationship("Driver", secondary=dispatch_group_drivers, back_populates="dispatch_groups", lazy="selectin")
    contractors = relationship("Contractor", secondary=dispatch_group_contractors, back_populates="dispatch_groups", lazy="selectin")
    tours = relationship("Tour", back_populates="dispatch_group")
    users = relationship("User", secondary=dispatch_group_users, back_populates="dispatch_groups", lazy="selectin")
    default_contractor = relationship("Contractor", foreign_keys=[default_contractor_id])
    rules = relationship("DispatchGroupRule", back_populates="dispatch_group", cascade="all, delete-orphan", order_by="DispatchGroupRule.priority")


class DispatchGroupRule(Base):
    __tablename__ = "dispatch_group_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispatch_group_id: Mapped[int] = mapped_column(ForeignKey("dispatch_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, default="Fahrzeug")
    field_name: Mapped[str] = mapped_column(String(50), nullable=False, default="MatchCode")
    operator: Mapped[str] = mapped_column(String(30), nullable=False, default="enthält")
    comparison_value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    dispatch_group = relationship("DispatchGroup", back_populates="rules")
