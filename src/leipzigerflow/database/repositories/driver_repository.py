from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from leipzigerflow.models.driver import Driver


class DriverRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all(self, include_archived: bool = False) -> list[Driver]:
        stmt = select(Driver)
        if not include_archived:
            stmt = stmt.where(Driver.active.is_(True))
        stmt = stmt.order_by(Driver.active.desc(), Driver.last_name, Driver.first_name)
        return list(self._session.scalars(stmt))

    def get(self, driver_id: int) -> Driver | None:
        return self._session.get(Driver, driver_id)

    def search(self, text: str, include_archived: bool = False) -> list[Driver]:
        text = text.strip()
        if not text:
            return self.get_all(include_archived=include_archived)
        pattern = f"%{text}%"
        full_name = Driver.first_name + " " + Driver.last_name
        stmt = select(Driver).where(
            or_(
                Driver.match_code.ilike(pattern),
                Driver.personnel_number.ilike(pattern),
                Driver.modulon_driver_number.ilike(pattern),
                Driver.first_name.ilike(pattern),
                Driver.last_name.ilike(pattern),
                full_name.ilike(pattern),
                Driver.city.ilike(pattern),
                Driver.phone.ilike(pattern),
                Driver.mobile.ilike(pattern),
                Driver.email.ilike(pattern),
                Driver.license_number.ilike(pattern),
                Driver.license_classes.ilike(pattern),
            )
        )
        if not include_archived:
            stmt = stmt.where(Driver.active.is_(True))
        stmt = stmt.order_by(Driver.active.desc(), Driver.last_name, Driver.first_name)
        return list(self._session.scalars(stmt))

    def exists_by_name(self, first_name: str, last_name: str, exclude_id: int | None = None) -> bool:
        stmt = select(Driver).where(
            func.lower(Driver.first_name) == first_name.lower(),
            func.lower(Driver.last_name) == last_name.lower(),
            Driver.active.is_(True),
        )
        if exclude_id is not None:
            stmt = stmt.where(Driver.id != exclude_id)
        return self._session.scalar(stmt) is not None

    def exists_by_license_number(self, license_number: str, exclude_id: int | None = None) -> bool:
        license_number = license_number.strip()
        if not license_number:
            return False
        stmt = select(Driver).where(
            func.lower(Driver.license_number) == license_number.lower(),
            Driver.active.is_(True),
        )
        if exclude_id is not None:
            stmt = stmt.where(Driver.id != exclude_id)
        return self._session.scalar(stmt) is not None

    def add(self, driver: Driver):
        self._session.add(driver)
        self._session.commit()
        self._session.refresh(driver)

    def update(self, driver: Driver):
        self._session.commit()
        self._session.refresh(driver)

    def delete(self, driver: Driver):
        self._session.delete(driver)
        self._session.commit()
