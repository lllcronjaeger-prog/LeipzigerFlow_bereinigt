from leipzigerflow.database.repositories.customer_repository import (
    CustomerRepository,
)
from leipzigerflow.models.customer import Customer


class CustomerService:
    def __init__(self, session):
        self.repository = CustomerRepository(session)

    # ---------------------------------------------------------
    # Lesen
    # ---------------------------------------------------------

    def get_all(self) -> list[Customer]:
        return self.repository.get_all()

    def get(
        self,
        customer_id: int,
    ) -> Customer | None:
        return self.repository.get(customer_id)

    # ---------------------------------------------------------
    # Suchen
    # ---------------------------------------------------------

    def search_customers(
        self,
        text: str,
    ) -> list[Customer]:
        """
        Durchsucht alle Kunden.

        Es wird gesucht in:
        - Name
        - Kurzname
        - Ort
        """
        return self.repository.search(text)

    # ---------------------------------------------------------
    # Schreiben
    # ---------------------------------------------------------

    def add(
        self,
        customer: Customer,
    ):

        self._validate(customer)

        self.repository.add(customer)

    def update(
        self,
        customer: Customer,
    ):

        self._validate(customer)

        self.repository.update(customer)

    def delete(
        self,
        customer: Customer,
    ):

        self.repository.delete(customer)

    # ---------------------------------------------------------
    # Validierung
    # ---------------------------------------------------------

    def _validate(
        self,
        customer: Customer,
    ):

        customer.name = customer.name.strip()
        customer.short_name = customer.short_name.strip()

        customer.street = customer.street.strip()
        customer.house_number = customer.house_number.strip()
        customer.postal_code = customer.postal_code.strip()
        customer.city = customer.city.strip()
        customer.country = customer.country.strip()

        customer.phone = customer.phone.strip()
        customer.email = customer.email.strip()
        customer.website = customer.website.strip()
        customer.vat_number = customer.vat_number.strip()

        if not customer.name:
            raise ValueError(
                "Bitte einen Kundennamen eingeben."
            )

        if not customer.city:
            raise ValueError(
                "Bitte einen Ort eingeben."
            )

        if self.repository.exists_by_name(
            customer.name,
            customer.id,
        ):
            raise ValueError(
                "Ein Kunde mit diesem Namen existiert bereits."
            )