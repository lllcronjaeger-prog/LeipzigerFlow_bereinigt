from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from leipzigerflow.models.tour import Tour
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.trailer import Trailer


class AiContextBuilder:
    def __init__(self, session: Session, max_records: int = 40):
        self.session = session
        self.max_records = max_records

    def build(self) -> str:
        today = date.today()
        orders = self.session.scalars(
            select(TransportOrder)
            .where(TransportOrder.loading_date.between(today - timedelta(days=2), today + timedelta(days=14)))
            .order_by(TransportOrder.loading_date, TransportOrder.id)
            .limit(self.max_records)
        ).all()
        tours = self.session.scalars(
            select(Tour)
            .where(Tour.tour_date.between(today - timedelta(days=2), today + timedelta(days=14)))
            .order_by(Tour.tour_date, Tour.id)
            .limit(self.max_records)
        ).all()
        counts = {
            "Fahrer": len(self.session.scalars(select(Driver)).all()),
            "Fahrzeuge": len(self.session.scalars(select(Vehicle)).all()),
            "Trailer": len(self.session.scalars(select(Trailer)).all()),
        }
        lines = [
            "Aktueller LeipzigerFlow-Datenkontext (nur lesen):",
            ", ".join(f"{name}: {count}" for name, count in counts.items()),
            "",
            "Transportaufträge:",
        ]
        for order in orders:
            lines.append(
                f"- {order.order_number}; Status={order.status}; Laden={order.loading_date}; "
                f"Entladen={order.unloading_date}; Lademeter={order.loading_meters}; "
                f"Gewicht_kg={order.weight_kg}; Priorität={order.dispatch_priority}; "
                f"von={getattr(order.loading_location, 'full_display', '')}; "
                f"nach={getattr(order.unloading_location, 'full_display', '')}"
            )
        lines.append("")
        lines.append("Touren:")
        for tour in tours:
            lines.append(
                f"- {tour.tour_number}; Datum={tour.tour_date}; Status={tour.status}; "
                f"Fahrer={tour.driver_display}; Fahrzeug={tour.vehicle_display}; "
                f"Trailer={tour.trailer_display}; Aufträge={tour.order_count}"
            )
        return "\n".join(lines)
