from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.models.trailer import Trailer


class TrailerRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all(self) -> list[Trailer]:
        return list(self._session.scalars(select(Trailer).order_by(Trailer.trailer_number)))

    def get(self, trailer_id: int) -> Trailer | None:
        return self._session.get(Trailer, trailer_id)

    def get_by_number(self, number: str) -> Trailer | None:
        return self._session.scalar(select(Trailer).where(func.upper(Trailer.trailer_number) == number.upper()))

    def get_by_license_plate(self, plate: str) -> Trailer | None:
        return self._session.scalar(select(Trailer).where(func.upper(Trailer.license_plate) == plate.upper()))

    def add(self, trailer: Trailer):
        self._session.add(trailer); self._session.commit(); self._session.refresh(trailer)

    def update(self, trailer: Trailer):
        self._session.commit(); self._session.refresh(trailer)

    def delete(self, trailer: Trailer):
        self._session.delete(trailer); self._session.commit()
