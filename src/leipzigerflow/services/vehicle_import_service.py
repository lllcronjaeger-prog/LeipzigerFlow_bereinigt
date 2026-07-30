from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.vehicle_excel import FleetImportPreview, FleetImportRow
from leipzigerflow.models.trailer import Trailer, TrailerType
from leipzigerflow.models.vehicle import (
    Vehicle,
    VehicleClass,
    VehicleOperationType,
    VehicleOwnership,
)


@dataclass(slots=True)
class FleetImportResult:
    vehicles_created: int = 0
    vehicles_updated: int = 0
    trailers_created: int = 0
    trailers_updated: int = 0
    skipped: int = 0


class VehicleImportService:
    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: FleetImportPreview) -> FleetImportPreview:
        vehicle_plates = {
            value.casefold()
            for value in self.session.scalars(select(Vehicle.license_plate))
        }
        trailer_plates = {
            value.casefold()
            for value in self.session.scalars(select(Trailer.license_plate))
        }
        vehicle_numbers = {
            value.casefold()
            for value in self.session.scalars(select(Vehicle.vehicle_number))
        }
        trailer_numbers = {
            value.casefold()
            for value in self.session.scalars(select(Trailer.trailer_number))
        }

        for row in preview.rows:
            if row.errors:
                row.status = "Fehler"
                continue
            plate_key = row.license_plate.casefold()
            code_key = row.match_code.casefold()
            if row.is_vehicle:
                if plate_key in trailer_plates:
                    row.errors.append("Kennzeichen ist bereits als Trailer vorhanden")
                    row.status = "Fehler"
                elif plate_key in vehicle_plates:
                    row.status = "Update"
                elif code_key in vehicle_numbers:
                    row.errors.append("MatchCode ist bereits einer anderen Zugmaschine zugeordnet")
                    row.status = "Fehler"
                else:
                    row.status = "Neu"
            else:
                if plate_key in vehicle_plates:
                    row.errors.append("Kennzeichen ist bereits als Zugmaschine vorhanden")
                    row.status = "Fehler"
                elif plate_key in trailer_plates:
                    row.status = "Update"
                elif code_key in trailer_numbers:
                    row.errors.append("MatchCode ist bereits einem anderen Trailer zugeordnet")
                    row.status = "Fehler"
                else:
                    row.status = "Neu"
        return preview

    def import_rows(self, rows: list[FleetImportRow]) -> FleetImportResult:
        result = FleetImportResult()
        try:
            for row in rows:
                if not row.is_valid:
                    result.skipped += 1
                    continue
                if row.is_vehicle:
                    self._import_vehicle(row, result)
                else:
                    self._import_trailer(row, result)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def _import_vehicle(self, row: FleetImportRow, result: FleetImportResult) -> None:
        vehicle = self.session.scalar(
            select(Vehicle).where(func.lower(Vehicle.license_plate) == row.license_plate.lower())
        )
        if vehicle is None:
            vehicle = Vehicle(license_plate=row.license_plate)
            self.session.add(vehicle)
            result.vehicles_created += 1
        else:
            result.vehicles_updated += 1
        vehicle.vehicle_number = row.match_code
        vehicle.license_plate = row.license_plate
        vehicle.vehicle_class = VehicleClass.STANDARD.value
        vehicle.description = ""
        vehicle.operation_type = VehicleOperationType.LOCAL.value
        vehicle.home_base = "Ettlingen"
        vehicle.daily_return_required = True
        vehicle.overnight_away_allowed = False
        vehicle.ownership_type = VehicleOwnership.OWN.value
        vehicle.status = "Frei"
        vehicle.active = True

    def _import_trailer(self, row: FleetImportRow, result: FleetImportResult) -> None:
        trailer = self.session.scalar(
            select(Trailer).where(func.lower(Trailer.license_plate) == row.license_plate.lower())
        )
        if trailer is None:
            trailer = Trailer(
                trailer_number=row.match_code,
                license_plate=row.license_plate,
                trailer_type=TrailerType.PLANE.value,
            )
            self.session.add(trailer)
            result.trailers_created += 1
        else:
            result.trailers_updated += 1
        trailer.trailer_number = row.match_code
        trailer.license_plate = row.license_plate
        trailer.trailer_type = trailer.trailer_type or TrailerType.PLANE.value
        trailer.status = "Frei"
        trailer.active = True
