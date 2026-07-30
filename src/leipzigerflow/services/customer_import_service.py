from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.customer_excel import CustomerImportPreview, CustomerImportRow
from leipzigerflow.models.customer import Customer


@dataclass(slots=True)
class CustomerImportResult:
    created: int = 0
    updated: int = 0
    freight_payers_created: int = 0
    skipped: int = 0


class CustomerImportService:
    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: CustomerImportPreview) -> CustomerImportPreview:
        codes = {row.match_code.casefold() for row in preview.valid_rows if row.match_code}
        existing = set(self.session.scalars(select(func.lower(Customer.match_code)).where(func.lower(Customer.match_code).in_(codes)))) if codes else set()
        for row in preview.rows:
            row.status = "Update" if row.match_code.casefold() in existing else "Neu"
            if row.errors:
                row.status = "Fehler"
        return preview

    def import_rows(self, rows: list[CustomerImportRow]) -> CustomerImportResult:
        result = CustomerImportResult()
        try:
            payer_cache: dict[str, Customer] = {}
            for row in rows:
                if not row.is_valid:
                    result.skipped += 1
                    continue
                payer = self._get_or_create_freight_payer(row, payer_cache, result)
                customer = self.session.scalar(select(Customer).where(func.lower(Customer.match_code) == row.match_code.casefold()))
                if customer is None:
                    customer = Customer(name=row.name, match_code=row.match_code)
                    self.session.add(customer)
                    result.created += 1
                else:
                    result.updated += 1
                customer.name = row.name
                customer.short_name = row.match_code
                customer.match_code = row.match_code
                customer.street = row.street
                customer.house_number = row.house_number
                customer.postal_code = row.postal_code
                customer.city = row.city
                customer.country = row.country or "Deutschland"
                customer.freight_payer = payer if payer is not customer else None
                customer.active = True
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def _get_or_create_freight_payer(self, row, cache, result):
        code = row.freight_payer_match_code.strip()
        name = row.freight_payer_name.strip()
        if not code and not name:
            return None
        key = (code or name).casefold()
        if key in cache:
            return cache[key]
        payer = None
        if code:
            payer = self.session.scalar(select(Customer).where(func.lower(Customer.match_code) == code.casefold()))
        if payer is None and name:
            payer = self.session.scalar(select(Customer).where(func.lower(Customer.name) == name.casefold()))
        if payer is None:
            payer = Customer(name=name or code, short_name=code, match_code=code, city="", country="Deutschland", active=True)
            self.session.add(payer)
            self.session.flush()
            result.freight_payers_created += 1
        cache[key] = payer
        return payer
