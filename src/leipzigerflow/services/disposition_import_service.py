from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leipzigerflow.imports.disposition_excel import DispositionImportPreview, DispositionImportRow, ParsedAddress, normalize_plate
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.contractor import Contractor, ContractorType
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.disposition_import_rule import DispositionImportRule
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.warehouse import WarehouseGroup
from leipzigerflow.services.audit_context import audit_scope
from leipzigerflow.services.tour_resource_assignment_service import TourResourceAssignmentService


@dataclass(slots=True)
class DispositionImportResult:
    locations_created: int = 0
    locations_updated: int = 0
    customers_created: int = 0
    orders_created: int = 0
    orders_updated: int = 0
    tours_created: int = 0
    tours_updated: int = 0
    tour_assignments: int = 0
    contractors_created: int = 0
    subcontractor_orders: int = 0
    skipped: int = 0
    ignored_by_rule: int = 0
    open_disposition_orders: int = 0
    warnings: int = 0


class DispositionImportService:
    def __init__(self, session: Session):
        self.session = session

    def mark_existing(self, preview: DispositionImportPreview) -> DispositionImportPreview:
        self._ensure_default_rules()
        rules = list(self.session.scalars(
            select(DispositionImportRule)
            .where(DispositionImportRule.active.is_(True))
            .order_by(DispositionImportRule.priority, DispositionImportRule.id)
        ))
        customer_numbers = {
            row.customer_order_number.casefold()
            for row in preview.valid_rows
            if row.customer_order_number
        }
        transport_numbers = {
            row.transport_number.casefold()
            for row in preview.valid_rows
            if row.transport_number
        }
        existing_customers = set(self.session.scalars(
            select(func.lower(TransportOrder.customer_order_number)).where(
                func.lower(TransportOrder.customer_order_number).in_(customer_numbers)
            )
        )) if customer_numbers else set()
        existing_transports = set(self.session.scalars(
            select(func.lower(TransportOrder.transport_number)).where(
                func.lower(TransportOrder.transport_number).in_(transport_numbers)
            )
        )) if transport_numbers else set()
        for row in preview.rows:
            self._apply_import_rule(row, rules)
            if row.errors:
                row.status = "Fehler"
            elif row.rule_action == "Auftrag ignorieren":
                row.status = "Ignoriert"
            else:
                customer_key = row.customer_order_number.casefold()
                transport_key = row.transport_number.casefold()
                row.status = "Update" if (
                    (customer_key and customer_key in existing_customers)
                    or (not customer_key and transport_key in existing_transports)
                ) else "Neu"
        return preview

    def _ensure_default_rules(self) -> None:
        exists = self.session.scalar(select(DispositionImportRule.id).where(
            func.lower(DispositionImportRule.field_name) == "unternehmer",
            func.lower(DispositionImportRule.comparison_value) == "storno laut kunde",
            DispositionImportRule.action == "Auftrag ignorieren",
        ).limit(1))
        if exists is None:
            self.session.add(DispositionImportRule(
                name="Storno laut Kunde ignorieren", field_name="Unternehmer",
                operator="ist gleich", comparison_value="Storno laut Kunde",
                action="Auftrag ignorieren", priority=10, active=True,
            ))
            self.session.flush()

    @staticmethod
    def _normalize_rule_value(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip()).casefold()

    def _rule_matches(self, rule: DispositionImportRule, row: DispositionImportRow) -> bool:
        fields = {
            "Unternehmer": row.subcontractor, "Fahrzeug": row.vehicle,
            "Fahrer": row.driver, "Frachtzahler": row.freight_payer,
            "Beladestelle": row.loading_address.name, "Entladestelle": row.unloading_address.name,
        }
        actual = fields.get(rule.field_name, row.subcontractor) or ""
        expected = rule.comparison_value or ""
        a, e = self._normalize_rule_value(actual), self._normalize_rule_value(expected)
        if rule.operator == "ist gleich": return a == e
        if rule.operator == "enthält": return e in a
        if rule.operator == "beginnt mit": return a.startswith(e)
        if rule.operator == "endet mit": return a.endswith(e)
        if rule.operator == "Platzhalter":
            pattern = re.escape(e).replace(r"\*", ".*").replace(r"\?", ".")
            return re.fullmatch(pattern, a, flags=re.IGNORECASE) is not None
        if rule.operator == "Regex":
            try: return re.search(expected, actual, flags=re.IGNORECASE) is not None
            except re.error: return False
        return False

    def _apply_import_rule(self, row: DispositionImportRow, rules: list[DispositionImportRule]) -> None:
        row.rule_action = row.rule_name = row.responsibility_hint = row.replacement_contractor = row.ignored_reason = ""
        for rule in rules:
            if self._rule_matches(rule, row):
                row.rule_action = rule.action
                row.rule_name = rule.name
                row.responsibility_hint = rule.responsibility_hint
                row.replacement_contractor = rule.replacement_contractor
                if rule.action == "Auftrag ignorieren":
                    row.ignored_reason = f"Regel: {rule.name}"
                break

    def import_rows(self, rows: list[DispositionImportRow]) -> DispositionImportResult:
        result = DispositionImportResult()
        # Regeln werden beim eigentlichen Import erneut ausgewertet. Dadurch ist
        # der Schutz auch dann aktiv, wenn ein Aufruf die Vorschau/mark_existing
        # überspringt oder die Regel nach dem Erzeugen der Vorschau geändert wurde.
        self._ensure_default_rules()
        rules = list(self.session.scalars(
            select(DispositionImportRule)
            .where(DispositionImportRule.active.is_(True))
            .order_by(DispositionImportRule.priority, DispositionImportRule.id)
        ))
        try:
            for row in rows:
                self._apply_import_rule(row, rules)
                # Storno muss vor jeder Stammdaten-, Routing- oder Touranlage greifen.
                # Zusätzlich zur konfigurierbaren Regel wird der eindeutige Dispoplan-
                # Status robust über alle importierten Textfelder erkannt.
                if row.rule_action == "Auftrag ignorieren" or row.is_cancelled:
                    self._remove_existing_cancelled_order(row)
                    result.ignored_by_rule += 1
                    continue
                if not row.is_valid:
                    result.skipped += 1
                    continue
                customer = self._get_or_create_customer(row.freight_payer, result)
                loading = self._get_or_create_location(row.loading_address, customer, result)
                unloading = self._get_or_create_location(row.unloading_address, customer, result)
                order = self._find_existing_order(row)
                if order is None:
                    order = TransportOrder(
                        order_number=self._unique_internal_order_number(row),
                        customer_id=customer.id,
                        loading_location_id=loading.id,
                        unloading_location_id=unloading.id,
                        loading_date=row.loading_date,
                        unloading_date=row.unloading_date,
                    )
                    self.session.add(order)
                    self.session.flush()
                    result.orders_created += 1
                else:
                    result.orders_updated += 1
                raw_contractor = row.replacement_contractor or row.subcontractor
                contractor = None
                if row.rule_action not in {"Disposition offen", "Kein Subunternehmer", "Interner Hinweis"}:
                    contractor = self._get_or_create_contractor(raw_contractor, result)
                self._apply_order(order, row, customer, loading, unloading, contractor)
                if row.rule_action == "Disposition offen":
                    self._remove_from_own_tour(order)
                    result.open_disposition_orders += 1
                elif contractor is not None and contractor.is_own_fleet and row.has_planning:
                    self._assign_tour(order, row, result, contractor)
                else:
                    self._remove_from_own_tour(order)
                    if contractor is not None and not contractor.is_own_fleet:
                        result.subcontractor_orders += 1
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result


    def _remove_existing_cancelled_order(self, row: DispositionImportRow) -> None:
        """Entfernt einen bereits früher importierten, nun stornierten Auftrag.

        Dadurch verschwinden Stornos auch dann aus der Auftragsübersicht, wenn sie
        in einem älteren Import bereits angelegt wurden. Die Kundenauftragsnummer
        bleibt der führende Schlüssel; die Transportnummer dient nur als Fallback.
        """
        order = self._find_existing_order(row)
        if order is None:
            return
        positions = list(self.session.scalars(
            select(TourPosition).where(TourPosition.transport_order_id == order.id)
        ))
        for position in positions:
            self.session.delete(position)
        self.session.delete(order)
        self.session.flush()

    @staticmethod
    def _import_schedule_bounds(row: DispositionImportRow) -> tuple[datetime, datetime]:
        """Erzeugt belastbare Fahrerzeiten ohne Routing/Geocoding.

        Der Import darf keine Online-Routenberechnung auslösen, weil diese einen
        zweiten SQLite-Schreiber öffnet und den eigentlichen Import blockieren kann.
        """
        start_day = row.loading_date or date.today()
        end_day = row.unloading_date or start_day
        start_at = datetime.combine(start_day, row.loading_time_from or datetime.min.time())
        if row.unloading_time_until is not None:
            end_at = datetime.combine(end_day, row.unloading_time_until)
        elif row.unloading_time_from is not None:
            end_at = datetime.combine(end_day, row.unloading_time_from)
        elif row.loading_time_until is not None:
            end_at = datetime.combine(start_day, row.loading_time_until)
        else:
            end_at = start_at + timedelta(hours=10)
        if end_at <= start_at:
            end_at = start_at + timedelta(hours=10)
        return start_at, end_at

    def _find_existing_order(self, row: DispositionImportRow) -> TransportOrder | None:
        """Kundenauftragsnummer ist der führende fachliche Synchronisationsschlüssel.

        Nur für Altdaten oder interne Aufträge ohne Kundenauftragsnummer wird auf
        die technische Transportnummer zurückgefallen. Die Dossiernummer ist
        ausdrücklich kein eindeutiger Schlüssel.
        """
        if row.customer_order_number:
            return self.session.scalar(
                select(TransportOrder)
                .where(func.lower(TransportOrder.customer_order_number) == row.customer_order_number.casefold())
                .order_by(TransportOrder.id)
                .limit(1)
            )
        if row.transport_number:
            order = self.session.scalar(
                select(TransportOrder)
                .where(func.lower(TransportOrder.transport_number) == row.transport_number.casefold())
                .order_by(TransportOrder.id)
                .limit(1)
            )
            if order is not None:
                return order
            # Kompatibilität mit Importen vor Einführung des eigenen Feldes.
            return self.session.scalar(
                select(TransportOrder)
                .where(func.lower(TransportOrder.order_number) == row.transport_number.casefold())
                .order_by(TransportOrder.id)
                .limit(1)
            )
        return None

    def _unique_internal_order_number(self, row: DispositionImportRow) -> str:
        base = (row.customer_order_number or row.transport_number or f"IMP-{row.source_row}").strip()
        base = re.sub(r"\s+", "-", base)[:30] or f"IMP-{row.source_row}"
        candidate = base
        counter = 1
        while self.session.scalar(
            select(TransportOrder.id).where(func.lower(TransportOrder.order_number) == candidate.casefold())
        ) is not None:
            counter += 1
            suffix = f"-{counter}"
            candidate = f"{base[:30-len(suffix)]}{suffix}"
        return candidate

    @staticmethod
    def _split_contractor(raw: str) -> tuple[str, str]:
        value = raw.strip() or "LLL-UNBEKANNT | Leipziger Logistik (nicht angegeben)"
        match_code, separator, name = value.partition(" | ")
        return match_code.strip()[:100], (name.strip() if separator else value)[:150]

    @staticmethod
    def _looks_like_own_fleet(match_code: str, name: str) -> bool:
        normalized = re.sub(r"[^A-Z0-9]", "", f"{match_code} {name}".upper())
        return "LLL" in normalized

    def _get_or_create_contractor(self, raw: str, result: DispositionImportResult) -> Contractor:
        match_code, name = self._split_contractor(raw)
        contractor = self.session.scalar(select(Contractor).where(func.lower(Contractor.match_code) == match_code.casefold()))
        if contractor is None:
            contractor = Contractor(
                match_code=match_code, name=name,
                contractor_type=(ContractorType.OWN_FLEET.value if self._looks_like_own_fleet(match_code, name) else ContractorType.SUBCONTRACTOR.value),
                active=True,
            )
            self.session.add(contractor)
            self.session.flush()
            result.contractors_created += 1
        elif name and contractor.name != name:
            contractor.name = name
        return contractor

    def _remove_from_own_tour(self, order: TransportOrder) -> None:
        position = self.session.scalar(select(TourPosition).where(TourPosition.transport_order_id == order.id))
        if position is not None:
            self.session.delete(position)

    def _get_or_create_customer(self, freight_payer: str, result: DispositionImportResult) -> Customer:
        raw = freight_payer.strip() or "Unbekannter Frachtzahler"
        match_code, separator, name = raw.partition(" | ")
        display_name = (name if separator else raw).strip()
        short_name = match_code.strip() if separator else raw[:30]
        customer = self.session.scalar(select(Customer).where(func.lower(Customer.name) == display_name.casefold()))
        if customer is None:
            customer = Customer(name=display_name[:100], short_name=short_name[:30], active=True)
            self.session.add(customer)
            self.session.flush()
            result.customers_created += 1
        return customer

    def _get_or_create_location(self, address: ParsedAddress, customer: Customer, result: DispositionImportResult) -> Location:
        stmt = select(Location).where(
            func.lower(Location.name) == address.name.casefold(),
            func.lower(Location.postal_code) == address.postal_code.casefold(),
            func.lower(Location.city) == address.city.casefold(),
        )
        location = self.session.scalar(stmt)
        belongs_to_customer = self._belongs_to_customer(address.name, customer)
        location_type = LocationType.CUSTOMER if belongs_to_customer else LocationType.WAREHOUSE
        if location is None:
            group = None if belongs_to_customer else self._get_or_create_warehouse_group(address.name)
            location = Location(
                location_type=location_type,
                customer_id=customer.id if belongs_to_customer else None,
                warehouse_group_id=group.id if group else None,
                use_warehouse_group_defaults=bool(group),
                match_code=self._generate_location_match_code(address),
                name=address.name[:100], short_name=address.name[:30],
                street=address.street[:100], house_number=address.house_number[:20],
                postal_code=address.postal_code[:10], city=address.city[:100],
                country=address.country[:50], active=True,
            )
            self.session.add(location)
            if group is not None:
                location.warehouse_group = group
                location.apply_warehouse_group_defaults()
            self.session.flush()
            result.locations_created += 1
        else:
            changed = False
            if belongs_to_customer and location.location_type == LocationType.WAREHOUSE:
                location.location_type = LocationType.CUSTOMER
                location.customer_id = customer.id
                changed = True
            for field, value in (("street", address.street), ("house_number", address.house_number), ("postal_code", address.postal_code), ("city", address.city), ("country", address.country)):
                if value and getattr(location, field) != value:
                    setattr(location, field, value)
                    changed = True
            if changed:
                result.locations_updated += 1
        return location

    @staticmethod
    def _normalized_tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[A-ZÄÖÜ0-9]+", value.upper())
            if len(token) >= 4 and token not in {"GMBH", "AG", "KG", "LOGISTIK", "LAGER"}
        }

    def _belongs_to_customer(self, location_name: str, customer: Customer) -> bool:
        customer_text = " ".join(filter(None, (
            customer.name, customer.short_name, getattr(customer, "match_code", "")
        )))
        return bool(self._normalized_tokens(location_name) & self._normalized_tokens(customer_text))

    def _get_or_create_warehouse_group(self, location_name: str) -> WarehouseGroup | None:
        tokens = re.findall(r"[A-ZÄÖÜ0-9]+", location_name.upper())
        ignored = {"GMBH", "AG", "KG", "LOGISTIK", "ZENTRALLAGER", "LAGER"}
        group_name = next((token for token in tokens if len(token) >= 3 and token not in ignored), "")
        if not group_name:
            return None
        group = self.session.scalar(select(WarehouseGroup).where(func.lower(WarehouseGroup.name) == group_name.casefold()))
        if group is None:
            group = WarehouseGroup(name=group_name, aliases=location_name[:500], active=True)
            self.session.add(group)
            self.session.flush()
        return group

    def _generate_location_match_code(self, address: ParsedAddress) -> str:
        base_name = re.sub(r"[^A-Z0-9ÄÖÜ]", "", address.name.upper())[:12] or "LAGER"
        base = f"{base_name}-{address.postal_code or '00000'}"
        candidate = base[:100]
        suffix = 1
        while self.session.scalar(select(Location.id).where(func.lower(Location.match_code) == candidate.casefold())):
            suffix += 1
            candidate = f"{base[:94]}-{suffix}"
        return candidate

    @staticmethod
    def _apply_order(order: TransportOrder, row: DispositionImportRow, customer: Customer, loading: Location, unloading: Location, contractor: Contractor | None) -> None:
        order.customer_id = customer.id
        order.contractor_id = contractor.id if contractor else None
        order.contractor_raw = row.subcontractor
        order.import_rule_action = row.rule_action
        order.planning_owner_hint = row.responsibility_hint or (row.subcontractor if row.rule_action == "Disposition offen" else "")
        is_external_contractor = bool(contractor is not None and not contractor.is_own_fleet)
        # Ein im Dispoplan bereits an einen Subunternehmer vergebener Auftrag ist
        # fachlich disponiert. Er darf weder im offenen Pool noch in der
        # Auto-Disposition auftauchen. Nur eine ausdrückliche Importregel darf
        # ihn wieder für die interne Planung öffnen.
        order.auto_dispatch_eligible = (
            row.rule_action not in {"Auftrag ignorieren", "Fest an Subunternehmer vergeben"}
            and not is_external_contractor
        )
        if row.rule_action == "Disposition offen":
            order.assignment_type = "Disposition offen"
            order.auto_dispatch_eligible = True
        elif row.rule_action in {"Kein Subunternehmer", "Interner Hinweis"}:
            order.assignment_type = "Interner Hinweis"
            order.auto_dispatch_eligible = True
        else:
            order.assignment_type = contractor.contractor_type if contractor else "Eigener Fuhrpark"
        order.customer_order_number = row.customer_order_number
        order.transport_number = row.transport_number
        order.dossier = row.dossier
        order.loading_reference = row.loading_reference
        order.unloading_reference = row.unloading_reference
        # Das bisherige Referenzfeld bleibt für bestehende Ansichten kompatibel.
        order.reference = row.loading_reference or row.unloading_reference or row.dossier
        if row.is_cancelled:
            order.status = "Storniert"
        elif is_external_contractor:
            order.status = "Extern vergeben"
        elif row.rule_action == "Disposition offen":
            order.status = "Neu"
        else:
            order.status = "Geplant" if row.has_planning else "Neu"
        order.loading_location_id = loading.id
        order.loading_date = row.loading_date
        order.loading_time_from = row.loading_time_from
        order.loading_time_until = row.loading_time_until
        order.loading_original_from = row.loading_time_from
        order.loading_original_until = row.loading_time_until
        order.loading_time_flexible = True
        order.loading_window_status = "Unverändert"
        order.loading_window_change_reason = ""
        order.unloading_location_id = unloading.id
        order.unloading_date = row.unloading_date
        order.unloading_time_from = row.unloading_time_from
        order.unloading_time_until = row.unloading_time_until
        order.unloading_original_from = row.unloading_time_from
        order.unloading_original_until = row.unloading_time_until
        order.unloading_time_flexible = True
        order.unloading_window_status = "Unverändert"
        order.unloading_window_change_reason = ""
        order.weight_kg = row.weight_kg
        order.loading_meters = row.loading_meters
        order.pallets = row.pallets
        order.remarks = row.remarks


    @staticmethod
    def _normalize_driver_name(value: str) -> str:
        value = str(value or "").casefold().replace(",", " ")
        return " ".join(re.findall(r"[a-z0-9äöüß]+", value))

    def _find_driver(self, imported_name: str) -> Driver | None:
        normalized = self._normalize_driver_name(imported_name)
        if not normalized or "keiner" in normalized:
            return None
        imported_tokens = normalized.split()
        candidates = list(self.session.scalars(select(Driver).where(Driver.active.is_(True))))
        exact = []
        token_matches = []
        for driver in candidates:
            names = {
                self._normalize_driver_name(driver.full_name),
                self._normalize_driver_name(f"{driver.last_name} {driver.first_name}"),
                self._normalize_driver_name(driver.match_code),
            }
            names.discard("")
            if normalized in names:
                exact.append(driver)
                continue
            imported_set = set(imported_tokens)
            for name in names:
                name_set = set(name.split())
                if imported_set and (imported_set <= name_set or name_set <= imported_set):
                    token_matches.append(driver)
                    break
        if len(exact) == 1:
            return exact[0]
        unique_matches = {driver.id: driver for driver in token_matches}
        return next(iter(unique_matches.values())) if len(unique_matches) == 1 else None

    def _assign_tour(self, order: TransportOrder, row: DispositionImportRow, result: DispositionImportResult, contractor: Contractor) -> None:
        plate = normalize_plate(row.vehicle)
        vehicle = self.session.scalar(select(Vehicle).where(func.replace(func.replace(func.upper(Vehicle.license_plate), " ", ""), "-", "") == re.sub(r"[\s-]", "", plate)))
        driver = self._find_driver(row.driver)
        tour_number = self._tour_number(row.loading_date, plate)
        tour = self.session.scalar(select(Tour).where(func.lower(Tour.tour_number) == tour_number.casefold()))
        if tour is None:
            tour = Tour(tour_number=tour_number, tour_date=row.loading_date, planned_start_time=row.loading_time_from, status="Geplant", vehicle_id=vehicle.id if vehicle else None, driver_id=driver.id if driver else None, planning_locked=True, contractor_id=contractor.id, dispatch_group_id=vehicle.dispatch_group_id if vehicle else None, remarks="Automatisch aus Dispoplan-Disposition importiert")
            self.session.add(tour)
            self.session.flush()
            result.tours_created += 1
        else:
            tour.planned_start_time = row.loading_time_from or tour.planned_start_time
            tour.vehicle_id = vehicle.id if vehicle else tour.vehicle_id
            tour.driver_id = driver.id if driver else tour.driver_id
            tour.planning_locked = True
            tour.contractor_id = contractor.id
            if vehicle and vehicle.dispatch_group_id:
                tour.dispatch_group_id = vehicle.dispatch_group_id
            result.tours_updated += 1
        # Die Session arbeitet bewusst mit autoflush=False. Vor der Ermittlung
        # der nächsten Position müssen daher bereits vorgemerkte Zuordnungen
        # sichtbar gemacht werden, sonst erhalten mehrere Aufträge Position 1.
        self.session.flush()
        existing_position = self.session.scalar(
            select(TourPosition).where(TourPosition.transport_order_id == order.id)
        )
        if existing_position is None:
            max_position = self.session.scalar(
                select(func.max(TourPosition.position)).where(TourPosition.tour_id == tour.id)
            ) or 0
            self.session.add(TourPosition(
                tour_id=tour.id,
                transport_order_id=order.id,
                position=max_position + 1,
            ))
            self.session.flush()
            result.tour_assignments += 1
        elif existing_position.tour_id != tour.id:
            max_position = self.session.scalar(
                select(func.max(TourPosition.position)).where(TourPosition.tour_id == tour.id)
            ) or 0
            existing_position.tour_id = tour.id
            existing_position.position = max_position + 1
            self.session.flush()
            result.tour_assignments += 1
        resource_service = TourResourceAssignmentService(self.session)
        start_at, end_at = self._import_schedule_bounds(row)
        if driver is not None:
            resource_service.assign_driver_segments(
                tour,
                [{"driver_id": driver.id, "starts_at": start_at, "ends_at": end_at, "reason": "Dispositionsimport"}],
                propagate_last=False,
                commit=False,
            )
        else:
            # Stammfahrer/-trailer übernehmen, ohne während der Importtransaktion
            # TimePlanningEngine und damit Routing/Geocoding aufzurufen.
            resource_service.apply_vehicle_assignment_to_tour(
                tour, overwrite=False, schedule_bounds=(start_at, end_at)
            )

    @staticmethod
    def _tour_number(day: date, plate: str) -> str:
        compact = re.sub(r"[^A-Z0-9]", "", plate.upper())[-12:] or "UNBEKANNT"
        return f"DP-{day:%Y%m%d}-{compact}"[:30]
