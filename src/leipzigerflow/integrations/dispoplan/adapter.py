from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DispoplanSyncResult:
    imported_orders: int = 0
    imported_tours: int = 0
    imported_positions: int = 0
    completed_at: datetime | None = None
    message: str = ""


class DispoplanAdapter(ABC):
    """Stabile Schnittstelle für die spätere produktive Dispoplan-Anbindung."""

    @abstractmethod
    def import_open_orders(self) -> DispoplanSyncResult:
        raise NotImplementedError

    @abstractmethod
    def import_active_tours(self) -> DispoplanSyncResult:
        raise NotImplementedError

    @abstractmethod
    def export_confirmed_dispatch(self, assignments) -> DispoplanSyncResult:
        raise NotImplementedError


class MockDispoplanAdapter(DispoplanAdapter):
    def import_open_orders(self) -> DispoplanSyncResult:
        return DispoplanSyncResult(completed_at=datetime.now(), message="Mock-Import: lokale offene Aufträge werden verwendet.")

    def import_active_tours(self) -> DispoplanSyncResult:
        return DispoplanSyncResult(completed_at=datetime.now(), message="Mock-Import: lokale Touren werden verwendet.")

    def export_confirmed_dispatch(self, assignments) -> DispoplanSyncResult:
        return DispoplanSyncResult(completed_at=datetime.now(), message=f"Mock-Export: {len(assignments)} Zuordnungen nicht extern übertragen.")
