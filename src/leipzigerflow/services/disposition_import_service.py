from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.disposition_excel import DispositionImportPreview, DispositionImportRow, ParsedAddress, normalize_plate
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle


@dataclass(slots=True)
class DispositionImportResult:
    locations_created: int = 0
    locations_updated: int = 0
    customers_created: int = 0
    orders_created: int = 0
    orders_updated: int = 0
    tours_created: int = 0
    tours_updated: int = 0
    tour_assignments: int = 0
    skipped: int = 0


class DispositionImportService:
    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: DispositionImportPreview) -> DispositionImportPreview:
        numbers = {row.transport_number.casefold() for row in preview.valid_rows}
        existing = set(self.session.scalars(select(func.lower(TransportOrder.order_number)).where(func.lower(TransportOrder.order_number).in_(numbers)))) if numbers else set()
        for row in preview.rows:
            row.status = "Fehler" if row.errors else ("Update" if row.transport_number.casefold() in existing else "Neu")
        return preview

    def import_rows(self, rows: list[DispositionImportRow]) -> DispositionImportResult:
        result = DispositionImportResult()
        try:
            for row in rows:
                if not row.is_valid:
                    result.skipped += 1
                    continue
                customer = self._get_or_create_customer(row.freight_payer, result)
                loading = self._get_or_create_location(row.loading_address, LocationType.CUSTOMER, result)
                unloading = self._get_or_create_location(row.unloading_address, LocationType.CUSTOMER, result)
                order = self.session.scalar(select(TransportOrder).where(func.lower(TransportOrder.order_number) == row.transport_number.casefold()))
                if order is None:
                    order = TransportOrder(order_number=row.transport_number, customer_id=customer.id, loading_location_id=loading.id, unloading_location_id=unloading.id, loading_date=row.loading_date, unloading_date=row.unloading_date)
                    self.session.add(order)
                    self.session.flush()
                    result.orders_created += 1
                else:
                    result.orders_updated += 1
                self._apply_order(order, row, customer, loading, unloading)
                if row.has_planning:
                    self._assign_tour(order, row, result)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def _get_or_create_customer(self, freight_payer: str, result: DispositionImportResult) -> Customer:
        raw = freight_payer.strip() or "Unbekannter Frachtzahler"
        match_code, separator, name = raw.partition(" | ")
        display_name = (name if separator else raw).strip()
        short_name = match_code.strip() if separator else raw[:30]
        customer = self.session.scalar(select(Customer).where(func.lower(Customer.name) == display_name.casefold()))
        if customer is None:
            customer = Customer(name=display_name[:100], short_name=short_name[:30], active=True)
            self.session.add(customer)
            self.session.flush()
            result.customers_created += 1
        return customer

    def _get_or_create_location(self, address: ParsedAddress, location_type: LocationType, result: DispositionImportResult) -> Location:
        stmt = select(Location).where(func.lower(Location.name) == address.name.casefold(), func.lower(Location.postal_code) == address.postal_code.casefold(), func.lower(Location.city) == address.city.casefold())
        location = self.session.scalar(stmt)
        if location is None:
            location = Location(location_type=location_type, name=address.name[:100], short_name=address.name[:30], street=address.street[:100], house_number=address.house_number[:20], postal_code=address.postal_code[:10], city=address.city[:100], country=address.country[:50], active=True)
            self.session.add(location)
            self.session.flush()
            result.locations_created += 1
        else:
            changed = False
            for field, value in (("street", address.street), ("house_number", address.house_number), ("postal_code", address.postal_code), ("city", address.city), ("country", address.country)):
                if value and getattr(location, field) != value:
                    setattr(location, field, value)
                    changed = True
            if changed:
                result.locations_updated += 1
        return location

    @staticmethod
    def _apply_order(order: TransportOrder, row: DispositionImportRow, customer: Customer, loading: Location, unloading: Location) -> None:
        order.customer_id = customer.id
        order.customer_order_number = row.customer_order_number
        order.reference = row.loading_reference or row.unloading_reference or row.dossier
        order.status = "Storniert" if row.is_cancelled else ("Geplant" if row.has_planning else "Neu")
        order.loading_location_id = loading.id
        order.loading_date = row.loading_date
        order.loading_time_from = row.loading_time_from
        order.loading_time_until = row.loading_time_until
        order.loading_time_flexible = row.loading_time_from is None
        order.unloading_location_id = unloading.id
        order.unloading_date = row.unloading_date
        order.unloading_time_from = row.unloading_time_from
        order.unloading_time_until = row.unloading_time_until
        order.unloading_time_flexible = row.unloading_time_from is None
        order.weight_kg = row.weight_kg
        order.loading_meters = row.loading_meters
        order.pallets = row.pallets
        order.remarks = row.remarks

    def _assign_tour(self, order: TransportOrder, row: DispositionImportRow, result: DispositionImportResult) -> None:
        plate = normalize_plate(row.vehicle)
        vehicle = self.session.scalar(select(Vehicle).where(func.replace(func.replace(func.upper(Vehicle.license_plate), " ", ""), "-", "") == re.sub(r"[\s-]", "", plate)))
        driver = None
        if row.driver and "KEINER" not in row.driver.upper():
            driver = self.session.scalar(select(Driver).where(func.lower(func.trim(Driver.first_name + " " + Driver.last_name)) == row.driver.casefold()))
        tour_number = self._tour_number(row.loading_date, plate)
        tour = self.session.scalar(select(Tour).where(func.lower(Tour.tour_number) == tour_number.casefold()))
        if tour is None:
            tour = Tour(tour_number=tour_number, tour_date=row.loading_date, planned_start_time=row.loading_time_from, status="Geplant", vehicle_id=vehicle.id if vehicle else None, driver_id=driver.id if driver else None, planning_locked=True, remarks="Automatisch aus Dispoplan-Disposition importiert")
            self.session.add(tour)
            self.session.flush()
            result.tours_created += 1
        else:
            tour.planned_start_time = row.loading_time_from or tour.planned_start_time
            tour.vehicle_id = vehicle.id if vehicle else tour.vehicle_id
            tour.driver_id = driver.id if driver else tour.driver_id
            tour.planning_locked = True
            result.tours_updated += 1
        existing_position = self.session.scalar(select(TourPosition).where(TourPosition.transport_order_id == order.id))
        if existing_position is None:
            max_position = self.session.scalar(select(func.max(TourPosition.position)).where(TourPosition.tour_id == tour.id)) or 0
            self.session.add(TourPosition(tour_id=tour.id, transport_order_id=order.id, position=max_position + 1))
            result.tour_assignments += 1
        elif existing_position.tour_id != tour.id:
            existing_position.tour_id = tour.id
            max_position = self.session.scalar(select(func.max(TourPosition.position)).where(TourPosition.tour_id == tour.id)) or 0
            existing_position.position = max_position + 1
            result.tour_assignments += 1

    @staticmethod
    def _tour_number(day: date, plate: str) -> str:
        compact = re.sub(r"[^A-Z0-9]", "", plate.upper())[-12:] or "UNBEKANNT"
        return f"DP-{day:%Y%m%d}-{compact}"[:30]
