from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from leipzigerflow.database.base import Base


class DispositionImportRule(Base):
    """Pflegbare Regeln für die fachliche Einordnung von Dispoplan-Zeilen."""

    __tablename__ = "disposition_import_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    field_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Unternehmer")
    operator: Mapped[str] = mapped_column(String(30), nullable=False, default="ist gleich")
    comparison_value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="Disposition offen")
    responsibility_hint: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    replacement_contractor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
