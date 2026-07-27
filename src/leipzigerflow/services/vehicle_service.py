from sqlalchemy.orm import Session

from leipzigerflow.database.repositories.vehicle_repository import VehicleRepository
from leipzigerflow.models.vehicle import Vehicle, VehicleOperationType
from leipzigerflow.models.resource_absence import VehicleAbsence


class VehicleService:
    def __init__(self, session: Session):
        self.repository = VehicleRepository(session)

    def get_all(self) -> list[Vehicle]: return self.repository.get_all()
    def get(self, vehicle_id: int) -> Vehicle | None: return self.repository.get(vehicle_id)
    def add(self, vehicle: Vehicle): self._validate(vehicle); self.repository.add(vehicle)
    def update(self, vehicle: Vehicle): self._validate(vehicle); self.repository.update(vehicle)
    def delete(self, vehicle: Vehicle): self.repository.delete(vehicle)

    def replace_absences(self, vehicle: Vehicle, drafts) -> None:
        vehicle.absences.clear()
        for draft in drafts:
            vehicle.absences.append(VehicleAbsence(
                starts_at=draft.starts_at, ends_at=draft.ends_at, reason=draft.reason,
                remarks=draft.remarks, active=draft.active,
            ))
        self.repository.update(vehicle)

    def _validate(self, vehicle: Vehicle):
        vehicle.vehicle_number = vehicle.vehicle_number.strip().upper()
        vehicle.license_plate = vehicle.license_plate.strip().upper()
        vehicle.description = vehicle.description.strip()
        vehicle.location = vehicle.location.strip()
        vehicle.remarks = vehicle.remarks.strip()
        vehicle.home_base = (getattr(vehicle, "home_base", "") or "Ettlingen").strip()
        is_local = getattr(vehicle, "operation_type", VehicleOperationType.LOCAL.value) == VehicleOperationType.LOCAL.value
        vehicle.daily_return_required = bool(is_local)
        vehicle.overnight_away_allowed = not is_local
        profile = getattr(vehicle, "staffing_profile", None)
        if not is_local and profile is not None:
            profile.relief_driver_id = None
            profile.sequential_double_shift = False
        if not vehicle.vehicle_number:
            raise ValueError("Bitte eine Fahrzeugnummer eingeben.")
        if not vehicle.license_plate:
            raise ValueError("Bitte ein Kennzeichen eingeben.")
        existing = self.repository.get_by_license_plate(vehicle.license_plate)
        if existing is not None and existing.id != vehicle.id:
            raise ValueError("Dieses Kennzeichen existiert bereits.")
