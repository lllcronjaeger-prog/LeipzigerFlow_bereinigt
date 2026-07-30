from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.driver_excel import DriverImportPreview, DriverImportRow
from leipzigerflow.models.driver import Driver


@dataclass(slots=True)
class DriverImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0


class DriverImportService:
    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: DriverImportPreview) -> DriverImportPreview:
        codes = {row.match_code.lower() for row in preview.valid_rows if row.match_code}
        existing = set(
            self.session.scalars(
                select(func.lower(Driver.match_code)).where(func.lower(Driver.match_code).in_(codes))
            )
        ) if codes else set()
        for row in preview.rows:
            row.status = "Update" if row.match_code.lower() in existing else "Neu"
            if row.errors:
                row.status = "Fehler"
        return preview

    def import_rows(self, rows: list[DriverImportRow]) -> DriverImportResult:
        result = DriverImportResult()
        try:
            for row in rows:
                if not row.is_valid:
                    result.skipped += 1
                    continue
                driver = self.session.scalar(
                    select(Driver).where(func.lower(Driver.match_code) == row.match_code.lower())
                )
                if driver is None:
                    driver = Driver(match_code=row.match_code)
                    self.session.add(driver)
                    result.created += 1
                else:
                    result.updated += 1
                self._apply(driver, row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    @staticmethod
    def _apply(driver: Driver, row: DriverImportRow) -> None:
        driver.match_code = row.match_code
        driver.first_name = row.first_name
        driver.last_name = row.last_name
        driver.street = row.street
        driver.house_number = row.house_number
        driver.postal_code = row.postal_code
        driver.city = row.city
        driver.country = row.country or "Deutschland"
        driver.phone = row.phone
        driver.mobile = row.mobile
        driver.contact_raw = row.contact_raw
        driver.import_source = "Dispoplan Excel"
        driver.active = True
