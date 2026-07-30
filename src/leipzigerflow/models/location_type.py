from enum import Enum


class LocationType(str, Enum):
    CUSTOMER = "CUSTOMER"
    DEPOT = "DEPOT"
    WAREHOUSE = "WAREHOUSE"

    @property
    def display_name(self) -> str:
        return {
            LocationType.CUSTOMER: "🏭 Kunde",
            LocationType.DEPOT: "🏢 Eigenes Lager / Niederlassung",
            LocationType.WAREHOUSE: "📦 Lager",
        }[self]