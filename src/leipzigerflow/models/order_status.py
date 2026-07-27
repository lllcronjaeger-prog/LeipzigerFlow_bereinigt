from enum import Enum


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    @property
    def display_name(self) -> str:
        return {
            OrderStatus.OPEN: "Offen",
            OrderStatus.PLANNED: "Geplant",
            OrderStatus.IN_PROGRESS: "In Durchführung",
            OrderStatus.COMPLETED: "Abgeschlossen",
            OrderStatus.CANCELLED: "Storniert",
        }[self]