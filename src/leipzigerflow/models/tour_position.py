from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from leipzigerflow.database.base import Base


class TourPosition(Base):
    """Reihenfolge eines Transportauftrags innerhalb einer Tour."""

    __tablename__ = "tour_positions"
    __table_args__ = (
        UniqueConstraint(
            "transport_order_id",
            name="uq_tour_position_transport_order",
        ),
        UniqueConstraint(
            "tour_id",
            "position",
            name="uq_tour_position_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tour_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tours.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    transport_order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "transport_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )

    tour = relationship(
        "Tour",
        back_populates="positions",
    )
    transport_order = relationship(
        "TransportOrder",
    )

    def __repr__(self) -> str:
        return (
            "TourPosition("
            f"id={self.id}, "
            f"tour_id={self.tour_id}, "
            f"position={self.position}"
            ")"
        )
