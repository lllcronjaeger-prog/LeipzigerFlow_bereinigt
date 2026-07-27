from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from leipzigerflow.models.driver import Driver
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle


from leipzigerflow.services.trailer_compatibility import (
    requires_mega_only,
    requires_refrigeration_only,
)

OPEN_ORDER_STATUSES = {"Neu", "Offen", "In Planung"}
CLOSED_ORDER_STATUSES = {"Erledigt", "Storniert"}
AVAILABLE_STATUSES = {"Frei", "Auf dem Hof", "Verfügbar"}
WORKSHOP_STATUSES = {"Werkstatt", "Defekt"}
ACTIVE_TOUR_STATUSES = {"Geplant", "Unterwegs", "Beladung", "Entladung"}


@dataclass(slots=True)
class DashboardWarning:
    severity: str
    area: str
    title: str
    detail: str
    due_date: date | None = None


@dataclass(slots=True)
class DashboardRecommendation:
    severity: str
    title: str
    detail: str
    action: str


@dataclass(slots=True)
class DashboardSnapshot:
    generated_at: datetime
    active_drivers: int = 0
    available_drivers: int = 0
    absent_drivers: int = 0
    active_vehicles: int = 0
    available_vehicles: int = 0
    workshop_vehicles: int = 0
    active_trailers: int = 0
    available_trailers: int = 0
    workshop_trailers: int = 0
    open_orders: int = 0
    critical_orders: int = 0
    mega_orders: int = 0
    refrigerated_orders: int = 0
    tours_today: int = 0
    underway_tours: int = 0
    incomplete_tours: int = 0
    own_fleet_orders_today: int = 0
    own_fleet_planned_today: int = 0
    sales_orders_open: int = 0
    planning_quality: int = 100
    active_conflicts: int = 0
    recommendations: list[DashboardRecommendation] = field(default_factory=list)
    warnings: list[DashboardWarning] = field(default_factory=list)
    open_order_rows: list[TransportOrder] = field(default_factory=list)
    tour_rows: list[Tour] = field(default_factory=list)


class OperationsDashboardService:
    """Berechnet den aktuellen Betriebszustand für den Disponenten-Leitstand."""

    WARNING_DAYS = 60
    CRITICAL_DAYS = 14

    def build_snapshot(self, session: Session, today: date | None = None) -> DashboardSnapshot:
        today = today or date.today()
        now = datetime.now()

        drivers = list(session.scalars(select(Driver).order_by(Driver.last_name, Driver.first_name)))
        vehicles = list(session.scalars(select(Vehicle).options(joinedload(Vehicle.trailer))))
        trailers = list(session.scalars(select(Trailer)))
        tours = list(
            session.scalars(
                select(Tour)
                .options(
                    joinedload(Tour.driver),
                    joinedload(Tour.vehicle),
                    joinedload(Tour.trailer),
                    selectinload(Tour.positions),
                )
                .order_by(Tour.tour_date, Tour.planned_start_time, Tour.tour_number)
            ).unique()
        )
        orders = list(
            session.scalars(
                select(TransportOrder)
                .options(
                    joinedload(TransportOrder.customer),
                    joinedload(TransportOrder.loading_location),
                    joinedload(TransportOrder.unloading_location),
                )
                .order_by(
                    TransportOrder.loading_date,
                    TransportOrder.loading_time_from,
                    TransportOrder.order_number,
                )
            )
        )

        active_drivers = [driver for driver in drivers if driver.active]
        absent_drivers = [driver for driver in active_drivers if self._is_absent(driver, today)]
        available_drivers = [driver for driver in active_drivers if driver not in absent_drivers]

        active_vehicles = [vehicle for vehicle in vehicles if vehicle.active]
        available_vehicles = [
            vehicle for vehicle in active_vehicles if vehicle.status in AVAILABLE_STATUSES
        ]
        workshop_vehicles = [
            vehicle for vehicle in active_vehicles if vehicle.status in WORKSHOP_STATUSES
        ]

        active_trailers = [trailer for trailer in trailers if trailer.active]
        available_trailers = [
            trailer for trailer in active_trailers if trailer.status in AVAILABLE_STATUSES
        ]
        workshop_trailers = [
            trailer for trailer in active_trailers if trailer.status in WORKSHOP_STATUSES
        ]

        # Nur tatsächlich noch disponierbare Aufträge gelten als offen.
        # Ein Auftrag mit Status „Unterwegs“ darf ebenso wenig im offenen Bestand
        # erscheinen wie ein Auftrag, der bereits Bestandteil einer laufenden Tour ist.
        planned_or_underway_order_ids = {
            position.transport_order_id
            for tour in tours
            if tour.status in {"Geplant", "Unterwegs"}
            for position in tour.positions
        }
        open_orders = [
            order
            for order in orders
            if order.status in OPEN_ORDER_STATUSES and order.id not in planned_or_underway_order_ids
        ]
        critical_orders = [order for order in open_orders if self._is_order_critical(order, today)]
        mega_orders = [order for order in open_orders if self._requires_mega(order)]
        refrigerated_orders = [order for order in open_orders if self._requires_refrigeration(order)]

        tours_today = [tour for tour in tours if tour.tour_date == today]
        underway_tours = [tour for tour in tours_today if tour.status == "Unterwegs"]
        incomplete_tours = [
            tour
            for tour in tours_today
            if tour.status in ACTIVE_TOUR_STATUSES
            and (tour.driver_id is None or tour.vehicle_id is None or tour.trailer_id is None)
        ]

        warnings: list[DashboardWarning] = []
        self._append_fleet_warnings(warnings, active_vehicles, active_trailers, today)
        self._append_driver_warnings(warnings, active_drivers, today)
        self._append_operational_warnings(
            warnings,
            critical_orders,
            mega_orders,
            refrigerated_orders,
            incomplete_tours,
            available_vehicles,
            available_trailers,
        )
        warnings.sort(key=self._warning_sort_key)

        own_fleet_orders_today = [
            order for order in orders
            if order.loading_date == today
            and order.dispatch_priority == "Eigenfuhrpark bevorzugt"
            and order.status not in CLOSED_ORDER_STATUSES
        ]
        own_fleet_planned_today = [
            order for order in own_fleet_orders_today
            if order.id in planned_or_underway_order_ids
        ]
        sales_orders_open = [
            order for order in open_orders
            if order.dispatch_priority == "Verkauf bevorzugt"
        ]
        coverage = (
            100
            if not own_fleet_orders_today
            else round(100 * len(own_fleet_planned_today) / len(own_fleet_orders_today))
        )
        planning_quality = max(0, min(100, coverage - 10 * len(incomplete_tours)))
        active_conflicts = sum(1 for warning in warnings if warning.severity == "critical")
        recommendations = self._build_recommendations(
            own_fleet_open=len(own_fleet_orders_today) - len(own_fleet_planned_today),
            sales_open=len(sales_orders_open),
            incomplete_tours=len(incomplete_tours),
            critical_orders=len(critical_orders),
            available_vehicles=len(available_vehicles),
            available_drivers=len(available_drivers),
        )

        return DashboardSnapshot(
            generated_at=now,
            active_drivers=len(active_drivers),
            available_drivers=len(available_drivers),
            absent_drivers=len(absent_drivers),
            active_vehicles=len(active_vehicles),
            available_vehicles=len(available_vehicles),
            workshop_vehicles=len(workshop_vehicles),
            active_trailers=len(active_trailers),
            available_trailers=len(available_trailers),
            workshop_trailers=len(workshop_trailers),
            open_orders=len(open_orders),
            critical_orders=len(critical_orders),
            mega_orders=len(mega_orders),
            refrigerated_orders=len(refrigerated_orders),
            tours_today=len(tours_today),
            underway_tours=len(underway_tours),
            incomplete_tours=len(incomplete_tours),
            own_fleet_orders_today=len(own_fleet_orders_today),
            own_fleet_planned_today=len(own_fleet_planned_today),
            sales_orders_open=len(sales_orders_open),
            planning_quality=planning_quality,
            active_conflicts=active_conflicts,
            recommendations=recommendations,
            warnings=warnings,
            open_order_rows=(critical_orders + [o for o in open_orders if o not in critical_orders])[:15],
            tour_rows=tours_today[:15],
        )

    @staticmethod
    def _is_absent(driver: Driver, today: date) -> bool:
        if not driver.absence_from and not driver.absence_until:
            return False
        start = driver.absence_from or date.min
        end = driver.absence_until or date.max
        return start <= today <= end

    @staticmethod
    def _is_order_critical(order: TransportOrder, today: date) -> bool:
        if order.loading_date < today:
            return True
        if order.loading_date == today and order.status in OPEN_ORDER_STATUSES:
            return True
        return False

    @staticmethod
    def _order_text(order: TransportOrder) -> str:
        return " ".join(
            str(value).lower()
            for value in (order.order_type, order.reference, order.remarks)
            if value
        )

    def _requires_mega(self, order: TransportOrder) -> bool:
        return requires_mega_only(getattr(order, "required_trailer_type", ""))

    def _requires_refrigeration(self, order: TransportOrder) -> bool:
        return requires_refrigeration_only(getattr(order, "required_trailer_type", ""))

    def _append_fleet_warnings(
        self,
        warnings: list[DashboardWarning],
        vehicles: list[Vehicle],
        trailers: list[Trailer],
        today: date,
    ) -> None:
        for vehicle in vehicles:
            self._append_due_date_warning(
                warnings,
                "Zugmaschine",
                vehicle.display_name or vehicle.license_plate,
                "HU",
                vehicle.hu_date,
                today,
            )
        for trailer in trailers:
            subject = trailer.display_name
            self._append_due_date_warning(warnings, "Trailer", subject, "HU", trailer.hu_date, today)
            self._append_due_date_warning(warnings, "Trailer", subject, "SP", trailer.sp_date, today)

    def _append_driver_warnings(
        self,
        warnings: list[DashboardWarning],
        drivers: list[Driver],
        today: date,
    ) -> None:
        for driver in drivers:
            subject = driver.full_name or f"Fahrer {driver.id}"
            self._append_due_date_warning(
                warnings, "Fahrer", subject, "Fahrerkarte", driver.driver_card_valid_until, today
            )
            self._append_due_date_warning(
                warnings, "Fahrer", subject, "Module 95", driver.module_95_valid_until, today
            )
            if self._is_absent(driver, today):
                detail = driver.absence_reason or "Abwesend"
                if driver.absence_until:
                    detail += f" bis {driver.absence_until:%d.%m.%Y}"
                warnings.append(DashboardWarning("info", "Fahrer", subject, detail))

    def _append_due_date_warning(
        self,
        warnings: list[DashboardWarning],
        area: str,
        subject: str,
        examination: str,
        due_date: date | None,
        today: date,
    ) -> None:
        if due_date is None:
            return
        days = (due_date - today).days
        if days > self.WARNING_DAYS:
            return
        if days < 0:
            severity = "critical"
            detail = f"{examination} seit {abs(days)} Tag(en) abgelaufen"
        elif days <= self.CRITICAL_DAYS:
            severity = "critical"
            detail = f"{examination} läuft in {days} Tag(en) ab"
        else:
            severity = "warning"
            detail = f"{examination} läuft in {days} Tag(en) ab"
        warnings.append(DashboardWarning(severity, area, subject, detail, due_date))

    @staticmethod
    def _append_operational_warnings(
        warnings: list[DashboardWarning],
        critical_orders: list[TransportOrder],
        mega_orders: list[TransportOrder],
        refrigerated_orders: list[TransportOrder],
        incomplete_tours: list[Tour],
        available_vehicles: list[Vehicle],
        available_trailers: list[Trailer],
    ) -> None:
        if critical_orders:
            warnings.append(
                DashboardWarning(
                    "critical",
                    "Disposition",
                    f"{len(critical_orders)} kritische offene Aufträge",
                    "Ladedatum erreicht oder überschritten",
                )
            )
        mega_vehicles = [vehicle for vehicle in available_vehicles if vehicle.is_mega]
        mega_trailers = [trailer for trailer in available_trailers if trailer.is_mega]
        if mega_orders and (not mega_vehicles or not mega_trailers):
            warnings.append(
                DashboardWarning(
                    "critical",
                    "Disposition",
                    f"{len(mega_orders)} Mega-Aufträge",
                    "Keine vollständige freie Mega-Kombination verfügbar",
                )
            )
        refrigerated_trailers = [trailer for trailer in available_trailers if trailer.is_refrigerated]
        if refrigerated_orders and not refrigerated_trailers:
            warnings.append(
                DashboardWarning(
                    "critical",
                    "Disposition",
                    f"{len(refrigerated_orders)} Kühlaufträge",
                    "Kein freier Kühler verfügbar",
                )
            )
        if incomplete_tours:
            warnings.append(
                DashboardWarning(
                    "warning",
                    "Touren",
                    f"{len(incomplete_tours)} unvollständige Touren heute",
                    "Fahrer, Zugmaschine oder Trailer fehlt",
                )
            )

    @staticmethod
    def _build_recommendations(
        *,
        own_fleet_open: int,
        sales_open: int,
        incomplete_tours: int,
        critical_orders: int,
        available_vehicles: int,
        available_drivers: int,
    ) -> list[DashboardRecommendation]:
        recommendations: list[DashboardRecommendation] = []
        if own_fleet_open:
            recommendations.append(
                DashboardRecommendation(
                    "warning",
                    f"{own_fleet_open} Eigenfuhrpark-Auftrag/-Aufträge noch offen",
                    "Auto-Disposition ausführen und zulässige Varianten vergleichen.",
                    "Plantafel öffnen",
                )
            )
        if incomplete_tours:
            recommendations.append(
                DashboardRecommendation(
                    "critical",
                    f"{incomplete_tours} Tour(en) unvollständig",
                    "Fahrer, Zugmaschine oder Trailer fehlen.",
                    "Touren prüfen",
                )
            )
        if critical_orders:
            recommendations.append(
                DashboardRecommendation(
                    "critical",
                    f"{critical_orders} dringende offene Aufträge",
                    "Ladedatum ist erreicht oder bereits überschritten.",
                    "Aufträge öffnen",
                )
            )
        if sales_open:
            recommendations.append(
                DashboardRecommendation(
                    "info",
                    f"{sales_open} Verkaufsauftrag/-Aufträge verfügbar",
                    "Für Subunternehmer vormerken; Eigenfuhrpark-Aufträge nicht verdrängen.",
                    "Aufträge öffnen",
                )
            )
        if available_vehicles > available_drivers:
            recommendations.append(
                DashboardRecommendation(
                    "warning",
                    "Weniger Fahrer als verfügbare Zugmaschinen",
                    f"{available_vehicles} Fahrzeuge stehen {available_drivers} Fahrern gegenüber.",
                    "Fahrer prüfen",
                )
            )
        return recommendations[:8]

    @staticmethod
    def _warning_sort_key(warning: DashboardWarning) -> tuple[int, date]:
        priority = {"critical": 0, "warning": 1, "info": 2}
        return priority.get(warning.severity, 9), warning.due_date or date.max
