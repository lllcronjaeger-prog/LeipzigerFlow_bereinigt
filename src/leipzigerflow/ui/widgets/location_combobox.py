from leipzigerflow.database.database import SessionLocal
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.services.location_service import LocationService
from leipzigerflow.ui.widgets.search_combobox import SearchComboBox


class LocationComboBox(SearchComboBox):
    """
    ComboBox zur Auswahl eines Standortes.

    Kann optional nur Kunden anzeigen.
    """

    def __init__(
        self,
        only_customers: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.only_customers = only_customers

        self.reload()

    def reload(self):
        """
        Lädt alle Standorte neu.
        """

        self.clear_items()

        with SessionLocal() as session:

            service = LocationService(session)

            locations = service.get_all()

            if self.only_customers:
                locations = [
                    l
                    for l in locations
                    if l.location_type == LocationType.CUSTOMER
                ]

            locations.sort(
                key=lambda l: (
                    l.short_name or l.name
                ).upper()
            )

            for location in locations:
                self.add_object(
                    location.full_display,
                    location,
                )

    def current_location(self):
        """
        Gibt den aktuell ausgewählten Standort zurück.
        """

        return self.current_object()

    def set_location(self, location):
        """
        Wählt einen Standort aus.
        """

        self.set_current_object(location)