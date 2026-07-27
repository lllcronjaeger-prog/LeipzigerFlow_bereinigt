from leipzigerflow.database.repositories.location_repository import (
    LocationRepository,
)
from leipzigerflow.models.location import Location


class LocationService:
    def __init__(self, session):
        self.repository = LocationRepository(session)

    def get_all(self) -> list[Location]:
        return self.repository.get_all()

    def get(self, location_id: int) -> Location | None:
        return self.repository.get(location_id)

    def search_locations(
        self,
        text: str,
    ) -> list[Location]:
        """
        Durchsucht alle Standorte.

        Es wird gesucht in:
        - Name
        - Kurzname
        - Aliases
        - Straße
        - PLZ
        - Ort
        """
        return self.repository.search(text)

    def add(
        self,
        location: Location,
    ):

        self._validate(location)

        self.repository.add(location)

    def update(
        self,
        location: Location,
    ):

        self._validate(location)

        self.repository.update(location)

    def delete(
        self,
        location: Location,
    ):

        self.repository.delete(location)

    def _validate(
        self,
        location: Location,
    ):

        location.name = location.name.strip()
        location.short_name = location.short_name.strip()
        location.aliases = location.aliases.strip()

        location.street = location.street.strip()
        location.house_number = location.house_number.strip()
        location.postal_code = location.postal_code.strip()
        location.city = location.city.strip()
        location.country = location.country.strip()

        location.contact_person = location.contact_person.strip()
        location.phone = location.phone.strip()
        location.email = location.email.strip()

        location.opening_hours = location.opening_hours.strip()
        location.time_window = location.time_window.strip()
        location.time_window_booking_required = bool(
            getattr(location, "time_window_booking_required", False)
        )
        location.loading_duration_minutes = max(0, int(location.loading_duration_minutes or 0))
        location.unloading_duration_minutes = max(0, int(location.unloading_duration_minutes or 0))

        if not location.name:
            raise ValueError(
                "Bitte einen Namen eingeben."
            )

        if not location.city:
            raise ValueError(
                "Bitte einen Ort eingeben."
            )