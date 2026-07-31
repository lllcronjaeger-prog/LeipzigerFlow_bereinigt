from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class TransportOrder(Base):
    """Transportauftrag für den eigenen Fuhrpark."""

    __tablename__ = "transport_orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Technische, von LeipzigerFlow vergebene Auftragsnummer.
    order_number: Mapped[str] = mapped_column(
        String(30, collation="NOCASE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Fachlich eindeutige Nummer des Kundenauftrags. Bei rein internen
    # Umfuhren darf sie ausnahmsweise leer bleiben.
    customer_order_number: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
        index=True,
    )
    # Technische Referenz aus dem Dispoplan. Sie ist nicht die führende
    # Nummer in der Disposition und kann mehrere Kundenaufträge bündeln.
    transport_number: Mapped[str] = mapped_column(
        String(100), default="", nullable=False, index=True
    )
    # Faktura-Sammelreferenz; mehrere Aufträge dürfen dasselbe Dossier haben.
    dossier: Mapped[str] = mapped_column(
        String(100), default="", nullable=False, index=True
    )
    loading_reference: Mapped[str] = mapped_column(
        String(150), default="", nullable=False
    )
    unloading_reference: Mapped[str] = mapped_column(
        String(150), default="", nullable=False
    )

    order_type: Mapped[str] = mapped_column(
        String(30),
        default="Transport",
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )
    reference: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="Neu",
        nullable=False,
        index=True,
    )
    dispatch_priority: Mapped[str] = mapped_column(
        String(40),
        default="Eigenfuhrpark bevorzugt",
        nullable=False,
        index=True,
    )
    required_trailer_type: Mapped[str] = mapped_column(
        String(200),
        default="Plane",
        nullable=False,
        index=True,
    )

    loading_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )
    loading_date: Mapped[date] = mapped_column(Date, nullable=False)
    loading_time_from: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    loading_time_until: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    loading_time_flexible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    loading_open_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    loading_open_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    loading_original_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    loading_original_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    loading_window_status: Mapped[str] = mapped_column(String(30), default="Unverändert", nullable=False)
    loading_window_change_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    unloading_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )
    unloading_date: Mapped[date] = mapped_column(Date, nullable=False)
    unloading_time_from: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    unloading_time_until: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    unloading_time_flexible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    unloading_open_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    unloading_open_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    unloading_original_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    unloading_original_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    unloading_window_status: Mapped[str] = mapped_column(String(30), default="Unverändert", nullable=False)
    unloading_window_change_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    loading_meters: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        default=Decimal("0"),
        nullable=False,
    )
    pallets: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    contractor_id: Mapped[int | None] = mapped_column(ForeignKey("contractors.id"), nullable=True, index=True)
    contractor_raw: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(30), default="Eigener Fuhrpark", nullable=False, index=True)
    auto_dispatch_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    planning_owner_hint: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    import_rule_action: Mapped[str] = mapped_column(String(50), default="", nullable=False)

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

    customer = relationship("Customer")
    contractor = relationship("Contractor", back_populates="orders")
    loading_location = relationship(
        "Location",
        foreign_keys=[loading_location_id],
    )
    unloading_location = relationship(
        "Location",
        foreign_keys=[unloading_location_id],
    )

    @property
    def search_text(self) -> str:
        values = [
            self.order_number,
            self.customer_order_number,
            self.dossier,
            self.transport_number,
            self.loading_reference,
            self.unloading_reference,
            self.order_type,
            self.reference,
            self.status,
            self.dispatch_priority,
            self.required_trailer_type,
            self.customer.display_name if self.customer else "",
            self.loading_location.full_display
            if self.loading_location
            else "",
            self.unloading_location.full_display
            if self.unloading_location
            else "",
            self.remarks,
        ]
        return " ".join(
            str(value).lower()
            for value in values
            if value
        )

    def __repr__(self) -> str:
        return (
            "TransportOrder("
            f"id={self.id}, "
            f"order_number='{self.order_number}'"
            ")"
        )
