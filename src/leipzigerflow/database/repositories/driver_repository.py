from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from leipzigerflow.models.driver import Driver


class DriverRepository:
    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ---------------------------------------------------------
    # Lesen
    # ---------------------------------------------------------

    def get_all(self) -> list[Driver]:
        stmt = (
            select(Driver)
            .order_by(
                Driver.last_name,
                Driver.first_name,
            )
        )

        return list(
            self._session.scalars(stmt)
        )

    def get(
        self,
        driver_id: int,
    ) -> Driver | None:
        return self._session.get(
            Driver,
            driver_id,
        )

    # ---------------------------------------------------------
    # Suchen
    # ---------------------------------------------------------

    def search(
        self,
        text: str,
    ) -> list[Driver]:
        text = text.strip()

        if not text:
            return self.get_all()

        pattern = f"%{text}%"

        full_name = (
            Driver.first_name
            + " "
            + Driver.last_name
        )

        stmt = (
            select(Driver)
            .where(
                or_(
                    Driver.match_code.ilike(pattern),
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
            .order_by(
                Driver.last_name,
                Driver.first_name,
            )
        )

        return list(
            self._session.scalars(stmt)
        )

    def exists_by_name(
        self,
        first_name: str,
        last_name: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(Driver).where(
            func.lower(Driver.first_name)
            == first_name.lower(),
            func.lower(Driver.last_name)
            == last_name.lower(),
        )

        if exclude_id is not None:
            stmt = stmt.where(
                Driver.id != exclude_id
            )

        return (
            self._session.scalar(stmt)
            is not None
        )

    def exists_by_license_number(
        self,
        license_number: str,
        exclude_id: int | None = None,
    ) -> bool:
        license_number = license_number.strip()

        if not license_number:
            return False

        stmt = select(Driver).where(
            func.lower(Driver.license_number)
            == license_number.lower()
        )

        if exclude_id is not None:
            stmt = stmt.where(
                Driver.id != exclude_id
            )

        return (
            self._session.scalar(stmt)
            is not None
        )

    # ---------------------------------------------------------
    # Schreiben
    # ---------------------------------------------------------

    def add(
        self,
        driver: Driver,
    ):
        self._session.add(driver)
        self._session.commit()
        self._session.refresh(driver)

    def update(
        self,
        driver: Driver,
    ):
        self._session.commit()
        self._session.refresh(driver)

    def delete(
        self,
        driver: Driver,
    ):
        self._session.delete(driver)
        self._session.commit()