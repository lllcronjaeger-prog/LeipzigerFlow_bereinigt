from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base


class Customer(Base):
    """Datenbankmodell für einen Kunden."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100, collation="NOCASE"),
        nullable=False,
        unique=True,
    )


    match_code: Mapped[str] = mapped_column(
        String(100, collation="NOCASE"),
        default="",
        nullable=False,
        index=True,
    )

    freight_payer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )

    short_name: Mapped[str] = mapped_column(
        String(30),
        default="",
        nullable=False,
    )

    street: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )

    house_number: Mapped[str] = mapped_column(
        String(20),
        default="",
        nullable=False,
    )

    postal_code: Mapped[str] = mapped_column(
        String(10),
        default="",
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )

    country: Mapped[str] = mapped_column(
        String(50),
        default="Deutschland",
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(50),
        default="",
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )

    website: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )

    vat_number: Mapped[str] = mapped_column(
        String(30),
        default="",
        nullable=False,
    )

    disposition_priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    own_fleet_preferred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    subcontracting_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    freight_payer = relationship("Customer", remote_side=[id], foreign_keys=[freight_payer_id])

    @property
    def display_name(self) -> str:
        """Kurze Anzeige für Listen und Comboboxen."""
        return self.short_name if self.short_name else self.name

    @property
    def full_address(self) -> str:
        """Komplette Kundenadresse."""

        lines = []

        street = f"{self.street} {self.house_number}".strip()

        if street:
            lines.append(street)

        city = f"{self.postal_code} {self.city}".strip()

        if city:
            lines.append(city)

        if self.country:
            lines.append(self.country)

        return "\n".join(lines)

    @property
    def search_text(self) -> str:
        """Zusammengefasster Suchtext."""

        values = [
            self.name,
            self.match_code,
            self.short_name,
            self.street,
            self.house_number,
            self.postal_code,
            self.city,
            self.country,
            self.phone,
            self.email,
            self.website,
            self.vat_number,
        ]

        return " ".join(
            value.lower()
            for value in values
            if value
        )

    def __repr__(self) -> str:
        return (
            f"Customer("
            f"id={self.id}, "
            f"name='{self.name}'"
            f")"
        )