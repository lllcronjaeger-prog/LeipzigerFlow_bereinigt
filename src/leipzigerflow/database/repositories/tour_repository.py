from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder


class TourRepository:
    """Datenbankzugriff für Touren und Tourpositionen."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _base_statement():
        return select(Tour).options(
            joinedload(Tour.driver),
            joinedload(Tour.vehicle),
            selectinload(Tour.positions).joinedload(
                TourPosition.transport_order
            ).joinedload(TransportOrder.customer),
            selectinload(Tour.positions).joinedload(
                TourPosition.transport_order
            ).joinedload(TransportOrder.loading_location),
            selectinload(Tour.positions).joinedload(
                TourPosition.transport_order
            ).joinedload(TransportOrder.unloading_location),
        )

    def get_all(self) -> list[Tour]:
        statement = self._base_statement().order_by(
            Tour.tour_date.desc(),
            Tour.tour_number.desc(),
        )
        return list(
            self._session.scalars(statement).unique()
        )

    def get(self, tour_id: int) -> Tour | None:
        statement = self._base_statement().where(
            Tour.id == tour_id
        )
        return self._session.scalars(
            statement
        ).unique().first()

    def get_tour_numbers_for_year(
        self,
        year: int,
    ) -> list[str]:
        prefix = f"T-{year}-"
        statement = select(Tour.tour_number).where(
            Tour.tour_number.like(f"{prefix}%")
        )
        return list(self._session.scalars(statement))

    def search(
        self,
        search_text: str = "",
        status: str = "",
    ) -> list[Tour]:
        term = search_text.strip().lower()
        tours = self.get_all()

        if term:
            tours = [
                tour
                for tour in tours
                if term in tour.search_text
            ]

        if status:
            tours = [
                tour
                for tour in tours
                if tour.status == status
            ]

        return tours

    def get_unassigned_orders(
        self,
    ) -> list[TransportOrder]:
        assigned_order_ids = select(
            TourPosition.transport_order_id
        )

        statement = (
            select(TransportOrder)
            .options(
                joinedload(TransportOrder.customer),
                joinedload(
                    TransportOrder.loading_location
                ),
                joinedload(
                    TransportOrder.unloading_location
                ),
            )
            .where(
                ~TransportOrder.id.in_(assigned_order_ids),
                TransportOrder.status.notin_(
                    ("Erledigt", "Storniert")
                ),
            )
            .order_by(
                TransportOrder.loading_date,
                TransportOrder.order_number,
            )
        )
        return list(self._session.scalars(statement))

    def add(self, tour: Tour) -> Tour:
        self._session.add(tour)
        self._session.commit()
        self._session.refresh(tour)
        return self.get(tour.id) or tour

    def update(self, tour: Tour) -> Tour:
        self._session.add(tour)
        self._session.commit()
        self._session.refresh(tour)
        return self.get(tour.id) or tour

    def delete(self, tour: Tour) -> None:
        self._session.delete(tour)
        self._session.commit()

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
