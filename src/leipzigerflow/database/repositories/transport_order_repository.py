from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder


class TransportOrderRepository:
    """Datenbankzugriff für Transportaufträge."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _base_statement():
        return select(TransportOrder).options(
            joinedload(TransportOrder.customer),
            joinedload(TransportOrder.loading_location),
            joinedload(TransportOrder.unloading_location),
        )

    def get_all(self) -> list[TransportOrder]:
        statement = self._base_statement().order_by(
            TransportOrder.loading_date.desc(),
            TransportOrder.order_number.desc(),
        )
        return list(self._session.scalars(statement))

    def get(self, order_id: int) -> TransportOrder | None:
        statement = self._base_statement().where(
            TransportOrder.id == order_id
        )
        return self._session.scalar(statement)

    def get_by_order_number(
        self,
        order_number: str,
    ) -> TransportOrder | None:
        statement = select(TransportOrder).where(
            TransportOrder.order_number == order_number
        )
        return self._session.scalar(statement)

    def get_order_numbers_for_year(
        self,
        year: int,
    ) -> list[str]:
        prefix = f"LF-{year}-"
        statement = select(TransportOrder.order_number).where(
            TransportOrder.order_number.like(f"{prefix}%")
        )
        return list(self._session.scalars(statement))

    def search(
        self,
        search_text: str = "",
        status: str = "",
        order_type: str = "",
    ) -> list[TransportOrder]:
        term = search_text.strip().lower()
        result = self.get_all()

        if term:
            result = [
                order
                for order in result
                if term in order.search_text
            ]

        if status:
            result = [
                order
                for order in result
                if order.status == status
            ]

        if order_type:
            result = [
                order
                for order in result
                if order.order_type == order_type
            ]

        return result

    def add(self, order: TransportOrder) -> TransportOrder:
        self._session.add(order)
        self._session.commit()
        self._session.refresh(order)
        return self.get(order.id) or order

    def add_many(
        self,
        orders: list[TransportOrder],
    ) -> list[TransportOrder]:
        self._session.add_all(orders)
        self._session.commit()

        result: list[TransportOrder] = []
        for order in orders:
            loaded = self.get(order.id)
            result.append(loaded or order)
        return result

    def update(self, order: TransportOrder) -> TransportOrder:
        self._session.add(order)
        self._session.commit()
        self._session.refresh(order)
        return self.get(order.id) or order

    def update_status_many(
        self,
        orders: list[TransportOrder],
        status: str,
    ) -> None:
        for order in orders:
            order.status = status
            self._session.add(order)
        self._session.commit()

    def delete_many(
        self,
        orders: list[TransportOrder],
    ) -> None:
        order_ids = [
            order.id
            for order in orders
            if order.id is not None
        ]
        if not order_ids:
            return

        positions = list(
            self._session.scalars(
                select(TourPosition).where(
                    TourPosition.transport_order_id.in_(
                        order_ids
                    )
                )
            )
        )
        affected_tour_ids = {
            position.tour_id
            for position in positions
        }

        # SQLite führt ON DELETE CASCADE nur bei aktivierten
        # Foreign Keys aus. Deshalb werden Tourpositionen hier
        # bewusst vor den Aufträgen entfernt.
        for position in positions:
            self._session.delete(position)

        self._session.flush()

        # Positionsnummern der betroffenen Touren wieder lückenlos
        # herstellen, damit Tourenplanung und Plantafel sauber laden.
        for tour_id in affected_tour_ids:
            remaining_positions = list(
                self._session.scalars(
                    select(TourPosition)
                    .where(
                        TourPosition.tour_id == tour_id
                    )
                    .order_by(TourPosition.position)
                )
            )
            for new_position, position in enumerate(
                remaining_positions,
                start=1,
            ):
                position.position = new_position

        for order in orders:
            self._session.delete(order)

        self._session.commit()

    def delete(self, order: TransportOrder) -> None:
        self.delete_many([order])
