from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from leipzigerflow.models.customer import Customer


class CustomerRepository:
    def __init__(self, session: Session):
        self._session = session

    # ---------------------------------------------------------
    # Lesen
    # ---------------------------------------------------------

    def get_all(self) -> list[Customer]:
        stmt = (
            select(Customer)
            .order_by(Customer.name)
        )

        return list(
            self._session.scalars(stmt)
        )

    def get(
        self,
        customer_id: int,
    ) -> Customer | None:
        return self._session.get(
            Customer,
            customer_id,
        )

    # ---------------------------------------------------------
    # Suchen
    # ---------------------------------------------------------

    def search(
        self,
        text: str,
    ) -> list[Customer]:

        text = text.strip()

        if not text:
            return self.get_all()

        pattern = f"%{text}%"

        stmt = (
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(pattern),
                    Customer.short_name.ilike(pattern),
                    Customer.city.ilike(pattern),
                )
            )
            .order_by(Customer.name)
        )

        return list(
            self._session.scalars(stmt)
        )

    def exists_by_name(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        Prüft, ob bereits ein Kunde mit diesem Namen existiert.
        Groß-/Kleinschreibung wird ignoriert.
        """

        stmt = select(Customer).where(
            func.lower(Customer.name) == name.lower()
        )

        if exclude_id is not None:
            stmt = stmt.where(
                Customer.id != exclude_id
            )

        return (
            self._session.scalar(stmt)
            is not None
        )

    # ---------------------------------------------------------
    # Schreiben
    # ---------------------------------------------------------

    def add(
        self,
        customer: Customer,
    ):

        self._session.add(customer)
        self._session.commit()
        self._session.refresh(customer)

    def update(
        self,
        customer: Customer,
    ):

        self._session.commit()
        self._session.refresh(customer)

    def delete(
        self,
        customer: Customer,
    ):

        self._session.delete(customer)
        self._session.commit()