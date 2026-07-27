from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from leipzigerflow.models.location import Location


class LocationRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all(self) -> list[Location]:
        stmt = (
            select(Location)
            .order_by(Location.name)
        )

        return list(
            self._session.scalars(stmt)
        )

    def get(
        self,
        location_id: int,
    ) -> Location | None:
        return self._session.get(
            Location,
            location_id,
        )

    def add(
        self,
        location: Location,
    ):
        self._session.add(location)
        self._session.commit()
        self._session.refresh(location)

    def update(
        self,
        location: Location,
    ):
        self._session.commit()
        self._session.refresh(location)

    def delete(
        self,
        location: Location,
    ):
        self._session.delete(location)
        self._session.commit()

    def search(
        self,
        text: str,
    ) -> list[Location]:
        """
        Sucht in

        - Name
        - Kurzname
        - Aliases
        - Straße
        - PLZ
        - Ort
        """

        text = text.strip()

        if not text:
            return self.get_all()

        pattern = f"%{text}%"

        stmt = (
            select(Location)
            .where(
                or_(
                    Location.name.ilike(pattern),
                    Location.short_name.ilike(pattern),
                    Location.aliases.ilike(pattern),
                    Location.street.ilike(pattern),
                    Location.postal_code.ilike(pattern),
                    Location.city.ilike(pattern),
                )
            )
            .order_by(Location.name)
        )

        return list(
            self._session.scalars(stmt)
        )