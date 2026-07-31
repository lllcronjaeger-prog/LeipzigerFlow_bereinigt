from datetime import date

from sqlalchemy import delete, select, update

from leipzigerflow.database.repositories.driver_repository import DriverRepository
from leipzigerflow.models.dispatch_group import dispatch_group_drivers
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.external_mapping import ExternalMapping
from leipzigerflow.models.resource_absence import DriverAbsence
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_driver_assignment import TourDriverAssignment
from leipzigerflow.models.vehicle_resource_assignment import VehicleResourceAssignment
from leipzigerflow.models.vehicle_staffing_profile import VehicleStaffingProfile


class DriverService:
    def __init__(self, session):
        self.repository = DriverRepository(session)

    @property
    def session(self):
        return self.repository._session

    def get_all(self, include_archived: bool = False) -> list[Driver]:
        return self.repository.get_all(include_archived=include_archived)

    def get(self, driver_id: int) -> Driver | None:
        return self.repository.get(driver_id)

    def search_drivers(self, text: str, include_archived: bool = False) -> list[Driver]:
        return self.repository.search(text, include_archived=include_archived)

    def add(self, driver: Driver):
        self._validate(driver)
        self.repository.add(driver)

    def update(self, driver: Driver):
        self._validate(driver)
        self.repository.update(driver)

    def delete(self, driver: Driver):
        self.repository.delete(driver)

    def archive(self, driver: Driver) -> None:
        driver.active = False
        self.repository.update(driver)

    def reactivate(self, driver: Driver) -> None:
        driver.active = True
        self._validate(driver)
        self.repository.update(driver)

    def merge(self, source: Driver, target: Driver) -> None:
        if source.id == target.id:
            raise ValueError("Quell- und Zielfahrer müssen unterschiedlich sein.")
        if not target.active:
            raise ValueError("Der Zielfahrer muss aktiv sein.")

        session = self.session
        try:
            # Fehlende Identifikatoren/Stammdaten des Zielfahrers ergänzen.
            transferable = (
                "personnel_number", "modulon_driver_number", "match_code", "phone", "mobile",
                "email", "license_number", "license_classes", "home_base", "home_base_location_id",
                "dispatch_group_id", "rotation_start",
            )
            for field in transferable:
                if not getattr(target, field, None) and getattr(source, field, None):
                    setattr(target, field, getattr(source, field))

            session.execute(update(Tour).where(Tour.driver_id == source.id).values(driver_id=target.id))
            session.execute(update(TourDriverAssignment).where(
                TourDriverAssignment.driver_id == source.id
            ).values(driver_id=target.id))
            session.execute(update(DriverAbsence).where(
                DriverAbsence.driver_id == source.id
            ).values(driver_id=target.id))
            session.execute(update(VehicleResourceAssignment).where(
                VehicleResourceAssignment.driver_id == source.id
            ).values(driver_id=target.id))
            session.execute(update(VehicleStaffingProfile).where(
                VehicleStaffingProfile.primary_driver_id == source.id
            ).values(primary_driver_id=target.id))
            session.execute(update(VehicleStaffingProfile).where(
                VehicleStaffingProfile.relief_driver_id == source.id
            ).values(relief_driver_id=target.id))
            session.execute(update(ExternalMapping).where(
                ExternalMapping.entity_type == "driver",
                ExternalMapping.internal_id == source.id,
            ).values(internal_id=target.id, match_method="Fahrer zusammengeführt"))

            target_group_ids = set(session.scalars(select(dispatch_group_drivers.c.dispatch_group_id).where(
                dispatch_group_drivers.c.driver_id == target.id
            )))
            source_group_ids = set(session.scalars(select(dispatch_group_drivers.c.dispatch_group_id).where(
                dispatch_group_drivers.c.driver_id == source.id
            )))
            for group_id in source_group_ids - target_group_ids:
                session.execute(dispatch_group_drivers.insert().values(
                    dispatch_group_id=group_id, driver_id=target.id
                ))
            session.execute(delete(dispatch_group_drivers).where(
                dispatch_group_drivers.c.driver_id == source.id
            ))

            source.active = False
            source.personnel_number = ""
            source.modulon_driver_number = ""
            source.match_code = source.match_code or f"ARCHIV-{source.id}"
            source.import_source = (source.import_source + " | Zusammengeführt in Fahrer #" + str(target.id)).strip(" |")
            session.commit()
            session.refresh(target)
            session.refresh(source)
        except Exception:
            session.rollback()
            raise

    def replace_absences(self, driver: Driver, drafts) -> None:
        driver.absences.clear()
        for draft in drafts:
            driver.absences.append(DriverAbsence(
                starts_at=draft.starts_at,
                ends_at=draft.ends_at,
                reason=draft.reason,
                remarks=draft.remarks,
                active=draft.active,
            ))
        self.repository.update(driver)

    def _validate(self, driver: Driver):
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
        driver.license_number = driver.license_number.strip()
        driver.license_classes = driver.license_classes.strip()
        driver.absence_reason = (driver.absence_reason or "").strip()

        if not driver.first_name:
            raise ValueError("Bitte einen Vornamen eingeben.")
        if not driver.last_name:
            raise ValueError("Bitte einen Nachnamen eingeben.")
        if not driver.city:
            raise ValueError("Bitte einen Ort eingeben.")
        if driver.active and self.repository.exists_by_name(driver.first_name, driver.last_name, driver.id):
            raise ValueError("Ein aktiver Fahrer mit diesem Namen existiert bereits.")
        if driver.active and driver.license_number and self.repository.exists_by_license_number(driver.license_number, driver.id):
            raise ValueError("Diese Führerscheinnummer ist bereits einem anderen aktiven Fahrer zugeordnet.")
        if driver.birth_date is not None and driver.birth_date > date.today():
            raise ValueError("Das Geburtsdatum darf nicht in der Zukunft liegen.")
        if driver.absence_from and driver.absence_until and driver.absence_until < driver.absence_from:
            raise ValueError("Das Ende der Abwesenheit darf nicht vor dem Beginn liegen.")
        if driver.license_valid_until is not None and driver.license_valid_until < date(1900, 1, 1):
            raise ValueError("Das Gültigkeitsdatum des Führerscheins ist ungültig.")
