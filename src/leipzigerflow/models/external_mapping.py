from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from leipzigerflow.database.base import Base


class ExternalMapping(Base):
    """Dauerhafte Zuordnung einer externen ID zu einem internen Stammdatensatz."""

    __tablename__ = "external_mappings"
    __table_args__ = (
        UniqueConstraint("source_system", "entity_type", "external_id", name="uq_external_mapping_source_entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(150), index=True)
    internal_id: Mapped[int] = mapped_column(Integer, index=True)
    external_label: Mapped[str] = mapped_column(String(255), default="")
    match_method: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
