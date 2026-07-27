from .vehicle import Vehicle
from .vehicle_staffing_profile import VehicleStaffingProfile
from .trailer import Trailer, TrailerType
from .location import Location
from .relation import Relation
from .route_cache import GeocodeCacheEntry, RouteCacheEntry

__all__ = ["Vehicle", "VehicleStaffingProfile", "Trailer", "TrailerType", "Location", "Relation", "RouteCacheEntry", "GeocodeCacheEntry", "AbsenceReason", "VehicleAbsence", "TrailerAbsence"]

from .resource_absence import AbsenceReason, VehicleAbsence, TrailerAbsence
