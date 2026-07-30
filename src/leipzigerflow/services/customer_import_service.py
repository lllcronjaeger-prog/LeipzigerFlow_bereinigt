from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.customer_excel import CustomerImportPreview, CustomerImportRow
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType


@dataclass(slots=True)
class CustomerImportResult:
    customers_created: int = 0
    customers_updated: int = 0
    locations_created: int = 0
    locations_updated: int = 0
    skipped: int = 0

    # Rückwärtskompatibilität für bestehende Aufrufer/Tests.
    @property
    def created(self) -> int:
        return self.locations_created

    @property
    def updated(self) -> int:
        return self.locations_updated

    @property
    def freight_payers_created(self) -> int:
        return self.customers_created


class CustomerImportService:
    """Importiert den Dispoplan-Kundenstamm in Kunde + Kundenstandorte.

    Der Wert aus ``Hauptkunde`` wird zum eigentlichen Kunden/Frachtzahler.
    Jede Excel-Zeile wird als Standort dieses Kunden gespeichert. Fehlt ein
    Hauptkunde, wird die Zeile selbst sowohl als Kunde als auch als Standort
    verwendet. So bleiben einzelne Kundenstämme ebenfalls importierbar.
    """

    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: CustomerImportPreview) -> CustomerImportPreview:
        for row in preview.rows:
            if row.errors:
                row.status = "Fehler"
                continue
            owner = self._find_owner(row)
            location = self._find_existing_location(row, owner) if owner else None
            row.status = "Standort aktualisieren" if location else "Standort neu"
        return preview

    def import_rows(self, rows: list[CustomerImportRow]) -> CustomerImportResult:
        result = CustomerImportResult()
        customer_cache: dict[str, Customer] = {}
        location_cache: dict[tuple[int, str], Location] = {}
        try:
            for row in rows:
                if not row.is_valid:
                    result.skipped += 1
                    continue

                customer = self._get_or_create_customer(row, customer_cache, result)
                self.session.flush()

                location_key = (customer.id, self._location_identity(row))
                location = location_cache.get(location_key)
                if location is None:
                    location = self._find_existing_location(row, customer)

                if location is None:
                    location = Location(
                        location_type=LocationType.CUSTOMER,
                        customer=customer,
                        name=row.name,
                    )
                    self.session.add(location)
                    result.locations_created += 1
                else:
                    result.locations_updated += 1

                self._apply_location_data(location, row, customer)
                location_cache[location_key] = location

                # Ist die Zeile zugleich der Hauptkunde, erhält auch der Kunde
                # die vollständige Anschrift aus dem Kundenstamm.
                if self._row_is_owner(row):
                    self._apply_customer_address(customer, row)

            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def _get_or_create_customer(
        self,
        row: CustomerImportRow,
        cache: dict[str, Customer],
        result: CustomerImportResult,
    ) -> Customer:
        code, name = self._owner_values(row)
        cache_key = (code or name).casefold()
        if cache_key in cache:
            return cache[cache_key]

        customer = self._find_customer(code, name)
        if customer is None:
            customer = Customer(
                name=name or code,
                short_name=code,
                match_code=code,
                city="",
                country=row.country or "Deutschland",
                active=True,
            )
            self.session.add(customer)
            result.customers_created += 1
        else:
            result.customers_updated += 1
            if code:
                customer.match_code = code
                customer.short_name = code
            if name:
                customer.name = name
            customer.active = True

        cache[cache_key] = customer
        return customer

    def _find_owner(self, row: CustomerImportRow) -> Customer | None:
        code, name = self._owner_values(row)
        return self._find_customer(code, name)

    def _find_customer(self, code: str, name: str) -> Customer | None:
        # SQLite lower() behandelt Umlaute nicht zuverlässig. Deshalb zuerst
        # exakt suchen und anschließend mit Python-casefold vergleichen.
        if code:
            customer = self.session.scalar(
                select(Customer).where(Customer.match_code == code)
            )
            if customer is not None:
                return customer
        if name:
            customer = self.session.scalar(
                select(Customer).where(Customer.name == name)
            )
            if customer is not None:
                return customer

        code_key = code.casefold()
        name_key = name.casefold()
        for customer in self.session.scalars(select(Customer)):
            if code_key and (customer.match_code or "").casefold() == code_key:
                return customer
            if name_key and (customer.name or "").casefold() == name_key:
                return customer
        return None

    def _find_existing_location(
        self,
        row: CustomerImportRow,
        customer: Customer | None,
    ) -> Location | None:
        if customer is None or customer.id is None:
            return None

        candidates = list(
            self.session.scalars(
                select(Location).where(Location.customer_id == customer.id)
            )
        )
        identity = self._location_identity(row)
        for location in candidates:
            if self._stored_location_identity(location) == identity:
                return location

        # Fallback für alte Datensätze ohne vollständige Anschrift.
        code_key = row.match_code.casefold()
        name_key = row.name.casefold()
        for location in candidates:
            has_complete_address = bool(
                location.postal_code and location.city
                and (location.street or location.house_number)
            )
            if (
                not has_complete_address
                and code_key
                and name_key
                and (location.short_name or "").casefold() == code_key
                and (location.name or "").casefold() == name_key
            ):
                return location
        return None

    @staticmethod
    def _owner_values(row: CustomerImportRow) -> tuple[str, str]:
        code = row.freight_payer_match_code.strip() or row.match_code.strip()
        name = row.freight_payer_name.strip() or row.name.strip()
        return code, name

    @staticmethod
    def _row_is_owner(row: CustomerImportRow) -> bool:
        code, name = CustomerImportService._owner_values(row)
        return (
            bool(code and row.match_code and code.casefold() == row.match_code.casefold())
            or bool(name and row.name and name.casefold() == row.name.casefold())
        )

    @staticmethod
    def _location_identity(row: CustomerImportRow) -> str:
        address = "|".join(
            part.strip().casefold()
            for part in (row.country, row.postal_code, row.city, row.street, row.house_number)
        )
        if address.strip("|"):
            return f"address:{address}"
        return f"name:{row.match_code.casefold()}|{row.name.casefold()}"

    @staticmethod
    def _stored_location_identity(location: Location) -> str:
        address = "|".join(
            (part or "").strip().casefold()
            for part in (
                location.country, location.postal_code, location.city,
                location.street, location.house_number,
            )
        )
        if address.strip("|"):
            return f"address:{address}"
        return f"name:{(location.short_name or '').casefold()}|{(location.name or '').casefold()}"

    @staticmethod
    def _apply_location_data(location: Location, row: CustomerImportRow, customer: Customer) -> None:
        location.location_type = LocationType.CUSTOMER
        location.customer = customer
        location.name = row.name
        if location.short_name and location.short_name.casefold() != row.match_code.casefold():
            aliases = {value.strip() for value in (location.aliases or "").split(";") if value.strip()}
            aliases.add(location.short_name)
            aliases.add(row.match_code)
            location.aliases = "; ".join(sorted(aliases, key=str.casefold))
        elif not location.short_name:
            location.short_name = row.match_code
        location.street = row.street
        location.house_number = row.house_number
        location.postal_code = row.postal_code
        location.city = row.city
        location.country = row.country or "Deutschland"
        location.active = True

    @staticmethod
    def _apply_customer_address(customer: Customer, row: CustomerImportRow) -> None:
        customer.street = row.street
        customer.house_number = row.house_number
        customer.postal_code = row.postal_code
        customer.city = row.city
        customer.country = row.country or "Deutschland"
