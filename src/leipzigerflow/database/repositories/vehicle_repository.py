from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from leipzigerflow.models.vehicle import Vehicle


class VehicleRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all(self) -> list[Vehicle]:
        stmt = (
            select(Vehicle)
            .options(joinedload(Vehicle.staffing_profile), joinedload(Vehicle.home_base_location))
            .order_by(Vehicle.vehicle_number, Vehicle.license_plate)
        )

        return list(self._session.scalars(stmt))

    def get(self, vehicle_id: int) -> Vehicle | None:
        return self._session.get(
            Vehicle,
            vehicle_id,
        )

    def get_by_license_plate(
        self,
        license_plate: str,
    ) -> Vehicle | None:

        stmt = (
            select(Vehicle)
            .where(
                func.upper(Vehicle.license_plate)
                == license_plate.upper()
            )
        )

        return self._session.scalar(stmt)

    def add(self, vehicle: Vehicle):

        self._session.add(vehicle)
        self._session.commit()
        self._session.refresh(vehicle)

    def update(self, vehicle: Vehicle):

        self._session.commit()
        self._session.refresh(vehicle)

    def delete(self, vehicle: Vehicle):

        self._session.delete(vehicle)
        self._session.commit()