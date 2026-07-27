from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from leipzigerflow.database.base import Base


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(primary_key=True)

    origin_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False
    )

    destination_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False
    )

    distance_km: Mapped[float] = mapped_column(
        nullable=False
    )

    def __repr__(self):
        return (
            f"Relation("
            f"{self.origin_location_id}"
            f" -> "
            f"{self.destination_location_id})"
        )