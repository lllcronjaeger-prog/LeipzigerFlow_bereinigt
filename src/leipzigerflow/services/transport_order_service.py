from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from leipzigerflow.database.repositories.transport_order_repository import (
    TransportOrderRepository,
)
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.services.trailer_compatibility import (
    parse_trailer_types,
    serialize_trailer_types,
)
from leipzigerflow.models.trailer import TrailerType


class TransportOrderValidationError(ValueError):
    pass


class TransportOrderService:
    STATUSES = (
        "Neu",
        "Geplant",
        "Unterwegs",
        "Erledigt",
        "Storniert",
    )

    TRAILER_TYPES = tuple(TrailerType.values())

    DISPATCH_PRIORITIES = (
        "Eigenfuhrpark bevorzugt",
        "Flexibel",
        "Verkauf bevorzugt",
    )

    ORDER_TYPES = (
        "Transport",
        "Umfuhr",
        "Shuttle",
        "Leerfahrt",
        "Sonderfahrt",
    )

    def __init__(self, session: Session):
        self.repository = TransportOrderRepository(session)

    def get_all(self) -> list[TransportOrder]:
        return self.repository.get_all()

    def get(self, order_id: int) -> TransportOrder | None:
        return self.repository.get(order_id)

    def search(
        self,
        search_text: str = "",
        status: str = "",
        order_type: str = "",
    ) -> list[TransportOrder]:
        return self.repository.search(
            search_text=search_text,
            status=status,
            order_type=order_type,
        )

    def create(self, data: dict[str, Any]) -> TransportOrder:
        cleaned = self._validate_and_clean(data)
        cleaned["order_number"] = self._next_order_number()
        return self.repository.add(TransportOrder(**cleaned))

    def update(
        self,
        order: TransportOrder,
        data: dict[str, Any],
    ) -> TransportOrder:
        cleaned = self._validate_and_clean(data)

        # Die interne Auftragsnummer wird beim Bearbeiten nie verändert.
        cleaned.pop("order_number", None)

        for field_name, value in cleaned.items():
            setattr(order, field_name, value)

        return self.repository.update(order)

    def update_status(
        self,
        order: TransportOrder,
        status: str,
    ) -> TransportOrder:
        self.update_status_many([order], status)
        return self.get(order.id) or order

    def update_status_many(
        self,
        orders: list[TransportOrder],
        status: str,
    ) -> None:
        status = str(status).strip()
        if status not in self.STATUSES:
            raise TransportOrderValidationError(
                "Der Auftragsstatus ist ungültig."
            )
        if not orders:
            return

        self.repository.update_status_many(
            orders,
            status,
        )

    def copy(self, source: TransportOrder) -> TransportOrder:
        data = self._copy_data(source)
        data["order_number"] = self._next_order_number()
        data["status"] = "Neu"
        return self.repository.add(TransportOrder(**data))

    def create_series(
        self,
        source: TransportOrder,
        count: int,
        interval_minutes: int = 0,
    ) -> list[TransportOrder]:
        if count < 1:
            raise TransportOrderValidationError(
                "Die Anzahl muss mindestens 1 betragen."
            )
        if count > 500:
            raise TransportOrderValidationError(
                "Es können höchstens 500 Aufträge auf einmal "
                "erzeugt werden."
            )
        if interval_minutes < 0:
            raise TransportOrderValidationError(
                "Der Zeitabstand darf nicht negativ sein."
            )

        orders: list[TransportOrder] = []
        reserved_numbers: set[str] = set()

        for index in range(count):
            data = self._copy_data(source)
            data["order_number"] = self._next_order_number(
                reserved_numbers
            )
            reserved_numbers.add(data["order_number"])
            data["status"] = "Neu"

            if interval_minutes:
                shift = timedelta(
                    minutes=index * interval_minutes
                )
                self._shift_schedule(data, shift)

            orders.append(TransportOrder(**data))

        return self.repository.add_many(orders)

    def delete_many(
        self,
        orders: list[TransportOrder],
    ) -> None:
        self.repository.delete_many(orders)

    def delete(self, order: TransportOrder) -> None:
        self.delete_many([order])

    def _next_order_number(
        self,
        reserved_numbers: set[str] | None = None,
    ) -> str:
        year = date.today().year
        prefix = f"LF-{year}-"
        existing = set(
            self.repository.get_order_numbers_for_year(year)
        )
        if reserved_numbers:
            existing.update(reserved_numbers)

        highest = 0
        for value in existing:
            if not value.startswith(prefix):
                continue
            suffix = value[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))

        return f"{prefix}{highest + 1:06d}"

    def _validate_and_clean(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        status = str(data.get("status", "Neu")).strip()
        if status not in self.STATUSES:
            raise TransportOrderValidationError(
                "Der Auftragsstatus ist ungültig."
            )

        dispatch_priority = str(
            data.get("dispatch_priority", "Eigenfuhrpark bevorzugt")
        ).strip()
        if dispatch_priority not in self.DISPATCH_PRIORITIES:
            raise TransportOrderValidationError(
                "Die Dispositionspriorität ist ungültig."
            )

        order_type = str(
            data.get("order_type", "Transport")
        ).strip()
        if order_type not in self.ORDER_TYPES:
            raise TransportOrderValidationError(
                "Der Auftragstyp ist ungültig."
            )

        requested_types = data.get(
            "required_trailer_types",
            data.get("required_trailer_type", TrailerType.PLANE.value),
        )
        if isinstance(requested_types, (list, tuple, set, frozenset)) and not requested_types:
            raise TransportOrderValidationError(
                "Bitte mindestens einen möglichen Trailertyp auswählen."
            )
        required_trailer_types = parse_trailer_types(requested_types)
        if not required_trailer_types:
            raise TransportOrderValidationError(
                "Bitte mindestens einen möglichen Trailertyp auswählen."
            )
        required_trailer_type = serialize_trailer_types(required_trailer_types)

        customer_id = self._required_positive_int(
            data.get("customer_id"),
            "Bitte einen Kunden auswählen.",
        )
        loading_location_id = self._required_positive_int(
            data.get("loading_location_id"),
            "Bitte eine Ladestelle auswählen.",
        )
        unloading_location_id = self._required_positive_int(
            data.get("unloading_location_id"),
            "Bitte eine Entladestelle auswählen.",
        )

        loading_date = data.get("loading_date")
        unloading_date = data.get("unloading_date")

        if not isinstance(loading_date, date):
            raise TransportOrderValidationError(
                "Bitte ein gültiges Ladedatum eingeben."
            )
        if not isinstance(unloading_date, date):
            raise TransportOrderValidationError(
                "Bitte ein gültiges Entladedatum eingeben."
            )
        if unloading_date < loading_date:
            raise TransportOrderValidationError(
                "Das Entladedatum darf nicht vor dem "
                "Ladedatum liegen."
            )

        loading_time_from = self._optional_time(
            data.get("loading_time_from")
        )
        loading_time_until = self._optional_time(
            data.get("loading_time_until")
        )
        unloading_time_from = self._optional_time(
            data.get("unloading_time_from")
        )
        unloading_time_until = self._optional_time(
            data.get("unloading_time_until")
        )
        loading_time_flexible = bool(data.get("loading_time_flexible", True))
        loading_open_from = self._optional_time(data.get("loading_open_from"))
        loading_open_until = self._optional_time(data.get("loading_open_until"))
        unloading_time_flexible = bool(data.get("unloading_time_flexible", True))
        unloading_open_from = self._optional_time(data.get("unloading_open_from"))
        unloading_open_until = self._optional_time(data.get("unloading_open_until"))

        if (
            loading_time_from
            and loading_time_until
            and loading_time_until < loading_time_from
        ):
            raise TransportOrderValidationError(
                "Das Ende des Ladezeitfensters liegt vor "
                "dem Beginn."
            )

        if loading_open_from and loading_open_until and loading_open_until < loading_open_from:
            raise TransportOrderValidationError("Das Ende der Lade-Öffnungszeit liegt vor dem Beginn.")
        if unloading_open_from and unloading_open_until and unloading_open_until < unloading_open_from:
            raise TransportOrderValidationError("Das Ende der Entlade-Öffnungszeit liegt vor dem Beginn.")

        if (
            unloading_time_from
            and unloading_time_until
            and unloading_time_until < unloading_time_from
        ):
            raise TransportOrderValidationError(
                "Das Ende des Entladezeitfensters liegt vor "
                "dem Beginn."
            )

        return {
            "dispatch_priority": dispatch_priority,
            "customer_order_number": str(
                data.get("customer_order_number", "")
            ).strip(),
            "dossier": str(data.get("dossier", "")).strip(),
            "transport_number": str(data.get("transport_number", "")).strip(),
            "loading_reference": str(data.get("loading_reference", "")).strip(),
            "unloading_reference": str(data.get("unloading_reference", "")).strip(),
            "order_type": order_type,
            "customer_id": customer_id,
            "reference": str(
                data.get("reference", "")
            ).strip(),
            "status": status,
            "required_trailer_type": required_trailer_type,
            "loading_location_id": loading_location_id,
            "loading_date": loading_date,
            "loading_time_from": loading_time_from,
            "loading_time_until": loading_time_until,
            "loading_time_flexible": loading_time_flexible,
            "loading_open_from": loading_open_from,
            "loading_open_until": loading_open_until,
            "unloading_location_id": unloading_location_id,
            "unloading_date": unloading_date,
            "unloading_time_from": unloading_time_from,
            "unloading_time_until": unloading_time_until,
            "unloading_time_flexible": unloading_time_flexible,
            "unloading_open_from": unloading_open_from,
            "unloading_open_until": unloading_open_until,
            "weight_kg": self._non_negative_decimal(
                data.get("weight_kg", 0),
                "Das Gewicht",
            ),
            "loading_meters": self._non_negative_decimal(
                data.get("loading_meters", 0),
                "Die Lademeter",
            ),
            "pallets": self._non_negative_int(
                data.get("pallets", 0),
                "Die Palettenanzahl",
            ),
            "remarks": str(
                data.get("remarks", "")
            ).strip(),
        }

    @staticmethod
    def _copy_data(
        source: TransportOrder,
    ) -> dict[str, Any]:
        return {
            "customer_order_number": (
                source.customer_order_number
            ),
            "dossier": getattr(source, "dossier", ""),
            "transport_number": getattr(source, "transport_number", ""),
            "loading_reference": getattr(source, "loading_reference", ""),
            "unloading_reference": getattr(source, "unloading_reference", ""),
            "order_type": source.order_type,
            "dispatch_priority": getattr(source, "dispatch_priority", "Eigenfuhrpark bevorzugt"),
            "customer_id": source.customer_id,
            "reference": source.reference,
            "status": "Neu",
            "required_trailer_type": source.required_trailer_type,
            "loading_location_id": (
                source.loading_location_id
            ),
            "loading_date": source.loading_date,
            "loading_time_from": source.loading_time_from,
            "loading_time_until": source.loading_time_until,
            "loading_time_flexible": getattr(source, "loading_time_flexible", True),
            "loading_open_from": getattr(source, "loading_open_from", None),
            "loading_open_until": getattr(source, "loading_open_until", None),
            "unloading_location_id": (
                source.unloading_location_id
            ),
            "unloading_date": source.unloading_date,
            "unloading_time_from": (
                source.unloading_time_from
            ),
            "unloading_time_until": (
                source.unloading_time_until
            ),
            "unloading_time_flexible": getattr(source, "unloading_time_flexible", True),
            "unloading_open_from": getattr(source, "unloading_open_from", None),
            "unloading_open_until": getattr(source, "unloading_open_until", None),
            "weight_kg": source.weight_kg,
            "loading_meters": source.loading_meters,
            "pallets": source.pallets,
            "remarks": source.remarks,
        }

    @classmethod
    def _shift_schedule(
        cls,
        data: dict[str, Any],
        shift: timedelta,
    ) -> None:
        loading_date = data["loading_date"]
        unloading_date = data["unloading_date"]

        loading_from_date, loading_from = cls._shift_date_time(
            loading_date,
            data["loading_time_from"],
            shift,
        )
        loading_until_date, loading_until = cls._shift_date_time(
            loading_date,
            data["loading_time_until"],
            shift,
        )

        unloading_from_date, unloading_from = cls._shift_date_time(
            unloading_date,
            data["unloading_time_from"],
            shift,
        )
        unloading_until_date, unloading_until = cls._shift_date_time(
            unloading_date,
            data["unloading_time_until"],
            shift,
        )

        data["loading_date"] = max(
            loading_from_date,
            loading_until_date,
        )
        data["loading_time_from"] = loading_from
        data["loading_time_until"] = loading_until

        data["unloading_date"] = max(
            unloading_from_date,
            unloading_until_date,
        )
        data["unloading_time_from"] = unloading_from
        data["unloading_time_until"] = unloading_until

    @staticmethod
    def _shift_date_time(
        current_date: date,
        current_time: time | None,
        shift: timedelta,
    ) -> tuple[date, time | None]:
        if current_time is None:
            return current_date, None

        shifted = (
            datetime.combine(current_date, current_time)
            + shift
        )
        return shifted.date(), shifted.time().replace(
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _required_positive_int(
        value: Any,
        message: str,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise TransportOrderValidationError(
                message
            ) from error

        if number <= 0:
            raise TransportOrderValidationError(message)
        return number

    @staticmethod
    def _non_negative_int(
        value: Any,
        label: str,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise TransportOrderValidationError(
                f"{label} muss eine ganze Zahl sein."
            ) from error

        if number < 0:
            raise TransportOrderValidationError(
                f"{label} darf nicht negativ sein."
            )
        return number

    @staticmethod
    def _non_negative_decimal(
        value: Any,
        label: str,
    ) -> Decimal:
        try:
            number = Decimal(str(value))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise TransportOrderValidationError(
                f"{label} muss eine Zahl sein."
            ) from error

        if number < 0:
            raise TransportOrderValidationError(
                f"{label} darf nicht negativ sein."
            )
        return number

    @staticmethod
    def _optional_time(value: Any) -> time | None:
        if value is None or isinstance(value, time):
            return value

        raise TransportOrderValidationError(
            "Ein Zeitfenster enthält eine ungültige Uhrzeit."
        )
