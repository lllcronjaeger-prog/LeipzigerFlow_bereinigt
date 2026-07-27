from datetime import date

from leipzigerflow.database.repositories.driver_repository import (
    DriverRepository,
)
from leipzigerflow.models.driver import Driver


class DriverService:
    def __init__(self, session):
        self.repository = DriverRepository(session)

    # ---------------------------------------------------------
    # Lesen
    # ---------------------------------------------------------

    def get_all(self) -> list[Driver]:
        return self.repository.get_all()

    def get(
        self,
        driver_id: int,
    ) -> Driver | None:
        return self.repository.get(driver_id)

    # ---------------------------------------------------------
    # Suchen
    # ---------------------------------------------------------

    def search_drivers(
        self,
        text: str,
    ) -> list[Driver]:
        return self.repository.search(text)

    # ---------------------------------------------------------
    # Schreiben
    # ---------------------------------------------------------

    def add(
        self,
        driver: Driver,
    ):
        self._validate(driver)
        self.repository.add(driver)

    def update(
        self,
        driver: Driver,
    ):
        self._validate(driver)
        self.repository.update(driver)

    def delete(
        self,
        driver: Driver,
    ):
        self.repository.delete(driver)

    # ---------------------------------------------------------
    # Validierung
    # ---------------------------------------------------------

    def _validate(
        self,
        driver: Driver,
    ):
        driver.first_name = driver.first_name.strip()
        driver.last_name = driver.last_name.strip()

        driver.street = driver.street.strip()
        driver.house_number = driver.house_number.strip()
        driver.postal_code = driver.postal_code.strip()
        driver.city = driver.city.strip()
        driver.country = driver.country.strip()

        driver.phone = driver.phone.strip()
        driver.mobile = driver.mobile.strip()
        driver.email = driver.email.strip()

        driver.license_number = (
            driver.license_number.strip()
        )
        driver.license_classes = (
            driver.license_classes.strip()
        )
        driver.absence_reason = (driver.absence_reason or "").strip()

        if not driver.first_name:
            raise ValueError(
                "Bitte einen Vornamen eingeben."
            )

        if not driver.last_name:
            raise ValueError(
                "Bitte einen Nachnamen eingeben."
            )

        if not driver.city:
            raise ValueError(
                "Bitte einen Ort eingeben."
            )

        if self.repository.exists_by_name(
            driver.first_name,
            driver.last_name,
            driver.id,
        ):
            raise ValueError(
                "Ein Fahrer mit diesem Namen "
                "existiert bereits."
            )

        if (
            driver.license_number
            and self.repository.exists_by_license_number(
                driver.license_number,
                driver.id,
            )
        ):
            raise ValueError(
                "Diese Führerscheinnummer ist bereits "
                "einem anderen Fahrer zugeordnet."
            )

        if (
            driver.birth_date is not None
            and driver.birth_date > date.today()
        ):
            raise ValueError(
                "Das Geburtsdatum darf nicht in der "
                "Zukunft liegen."
            )

        if driver.absence_from and driver.absence_until and driver.absence_until < driver.absence_from:
            raise ValueError("Das Ende der Abwesenheit darf nicht vor dem Beginn liegen.")

        if (
            driver.license_valid_until is not None
            and driver.license_valid_until
            < date(1900, 1, 1)
        ):
            raise ValueError(
                "Das Gültigkeitsdatum des Führerscheins "
                "ist ungültig."
            )