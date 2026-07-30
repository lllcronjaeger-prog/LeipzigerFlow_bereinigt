from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle


class AiContextBuilder:
    """Erzeugt einen kleinen, zur Frage passenden Read-only-Kontext."""

    def __init__(self, session: Session, max_records: int = 40):
        self.session = session
        self.max_records = max(5, max_records)

    def build(self, question: str = "") -> str:
        normalized = question.casefold()
        include_orders = self._matches(normalized, "auftrag", "ladung", "unverplant", "kapazität", "lademeter")
        include_tours = self._matches(normalized, "tour", "kritisch", "verspät", "planung", "disposition")
        include_drivers = self._matches(normalized, "fahrer", "personal", "frei", "verfügbar")
        include_vehicles = self._matches(normalized, "fahrzeug", "zugmaschine", "lkw", "frei", "verfügbar")
        include_trailers = self._matches(normalized, "trailer", "auflieger", "frei", "verfügbar")

        if not any((include_orders, include_tours, include_drivers, include_vehicles, include_trailers)):
            include_orders = include_tours = True

        lines = [
            "Aktueller LeipzigerFlow-Datenkontext (ausschließlich lesen):",
            self._count_summary(),
        ]
        per_section = max(3, min(self.max_records, 8))
        if include_orders:
            lines.extend(self._orders(per_section))
        if include_tours:
            lines.extend(self._tours(per_section))
        if include_drivers:
            lines.extend(self._drivers(per_section))
        if include_vehicles:
            lines.extend(self._vehicles(per_section))
        if include_trailers:
            lines.extend(self._trailers(per_section))
        return "\n".join(lines)[:5000]

    @staticmethod
    def _matches(question: str, *terms: str) -> bool:
        return any(term in question for term in terms)

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.session.scalar(statement) or 0)

    def _count_summary(self) -> str:
        counts = {
            "aktive Fahrer": self._count(Driver, Driver.active.is_(True)),
            "aktive Fahrzeuge": self._count(Vehicle, Vehicle.active.is_(True)),
            "aktive Trailer": self._count(Trailer, Trailer.active.is_(True)),
            "Touren gesamt": self._count(Tour),
            "Transportaufträge gesamt": self._count(TransportOrder),
        }
        return "Kennzahlen: " + ", ".join(f"{name}: {count}" for name, count in counts.items())

    def _orders(self, limit: int) -> list[str]:
        today = date.today()
        orders = self.session.scalars(
            select(TransportOrder)
            .where(TransportOrder.loading_date.between(today - timedelta(days=2), today + timedelta(days=14)))
            .order_by(TransportOrder.loading_date, TransportOrder.id)
            .limit(limit)
        ).all()
        lines = ["", f"Transportaufträge (maximal {limit} relevante Datensätze):"]
        for order in orders:
            lines.append(
                f"- {order.order_number}; Status={order.status}; Laden={order.loading_date}; "
                f"Entladen={order.unloading_date}; Lademeter={order.loading_meters}; "
                f"Gewicht_kg={order.weight_kg}; Priorität={order.dispatch_priority}; "
                f"von={getattr(order.loading_location, 'full_display', '')}; "
                f"nach={getattr(order.unloading_location, 'full_display', '')}"
            )
        return lines

    def _tours(self, limit: int) -> list[str]:
        today = date.today()
        tours = self.session.scalars(
            select(Tour)
            .where(Tour.tour_date.between(today - timedelta(days=2), today + timedelta(days=14)))
            .order_by(Tour.tour_date, Tour.id)
            .limit(limit)
        ).all()
        lines = ["", f"Touren (maximal {limit} relevante Datensätze):"]
        for tour in tours:
            lines.append(
                f"- {tour.tour_number}; Datum={tour.tour_date}; Status={tour.status}; "
                f"Fahrer={tour.driver_display}; Fahrzeug={tour.vehicle_display}; "
                f"Trailer={tour.trailer_display}; Aufträge={tour.order_count}"
            )
        return lines

    def _drivers(self, limit: int) -> list[str]:
        drivers = self.session.scalars(select(Driver).order_by(Driver.id).limit(limit)).all()
        lines = ["", f"Fahrer (maximal {limit} Datensätze):"]
        for driver in drivers:
            lines.append(f"- ID={driver.id}; Name={getattr(driver, 'full_name', str(driver))}; Aktiv={getattr(driver, 'is_active', '')}")
        return lines

    def _vehicles(self, limit: int) -> list[str]:
        vehicles = self.session.scalars(select(Vehicle).order_by(Vehicle.id).limit(limit)).all()
        lines = ["", f"Fahrzeuge (maximal {limit} Datensätze):"]
        for vehicle in vehicles:
            lines.append(f"- ID={vehicle.id}; Kennung={getattr(vehicle, 'display_name', str(vehicle))}; Aktiv={getattr(vehicle, 'is_active', '')}")
        return lines

    def _trailers(self, limit: int) -> list[str]:
        trailers = self.session.scalars(select(Trailer).order_by(Trailer.id).limit(limit)).all()
        lines = ["", f"Trailer (maximal {limit} Datensätze):"]
        for trailer in trailers:
            lines.append(f"- ID={trailer.id}; Kennung={getattr(trailer, 'display_name', str(trailer))}; Aktiv={getattr(trailer, 'is_active', '')}")
        return lines
