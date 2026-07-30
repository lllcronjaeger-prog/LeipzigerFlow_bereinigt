from enum import Enum

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leipzigerflow.database.base import Base
from leipzigerflow.models.location_type import LocationType


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    location_type: Mapped[LocationType] = mapped_column(
        SqlEnum(LocationType),
        nullable=False,
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )

    match_code: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
        index=True,
    )

    warehouse_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_groups.id"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    short_name: Mapped[str] = mapped_column(
        String(30),
        default="",
        nullable=False,
    )

    aliases: Mapped[str] = mapped_column(
        String(255),
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

    contact_person: Mapped[str] = mapped_column(
        String(100),
        default="",
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

    opening_hours: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )

    # Legacy-Feld aus frueheren Versionen. Es bleibt aus Kompatibilitaetsgruenden
    # erhalten, wird in der Benutzeroberflaeche aber nicht mehr verwendet.
    time_window: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )

    time_window_booking_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    loading_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    unloading_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    customer = relationship(
        "Customer",
        back_populates="locations",
        foreign_keys=[customer_id],
    )

    warehouse_group = relationship(
        "WarehouseGroup",
        back_populates="locations",
        foreign_keys=[warehouse_group_id],
    )

    @property
    def effective_opening_hours(self) -> str:
        """Individuelle Öffnungszeit oder Standard der Lagergruppe."""
        return self.opening_hours or (
            self.warehouse_group.monday_hours if self.warehouse_group else ""
        )

    @property
    def alias_list(self) -> list[str]:
        """Liefert die Aliases als Liste."""
        if not self.aliases.strip():
            return []

        return [
            alias.strip()
            for alias in self.aliases.split(";")
            if alias.strip()
        ]

    @property
    def display_name(self) -> str:
        """Kurze Anzeige für Listen und Comboboxen."""
        name = self.short_name if self.short_name else self.name
        return f"{self.location_type.display_name} {name}"

    @property
    def full_display(self) -> str:
        """Anzeige inklusive Ort."""
        name = self.short_name if self.short_name else self.name

        if self.city:
            return (
                f"{self.location_type.display_name} "
                f"{name} • {self.city}"
            )

        return (
            f"{self.location_type.display_name} "
            f"{name}"
        )

    @property
    def full_address(self) -> str:
        """Komplette Adresse."""

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
            self.aliases,
            self.street,
            self.house_number,
            self.postal_code,
            self.city,
            self.country,
        ]

        return " ".join(
            value.lower()
            for value in values
            if value
        )

    def __repr__(self) -> str:
        return (
            f"Location("
            f"id={self.id}, "
            f"name='{self.name}'"
            f")"
        )