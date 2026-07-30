from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.imports.customer_excel import build_preview
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.services.customer_import_service import CustomerImportService


def _workbook(tmp_path, rows):
    path = tmp_path / "kunden.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(["Name", "Matchcode", "Anschrift", "Hauptkunde"])
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_customer_import_creates_main_customer_and_linked_location(tmp_path):
    path = _workbook(tmp_path, [[
        "Coca-Cola, Halle", "COCAHALLE",
        "Coca Cola\nSchieferstraße 20\nD 06126 Halle",
        "COCABERL | Coca-Cola,BerlinKDFG",
    ]])
    preview = build_preview(path)
    row = preview.rows[0]
    assert row.street == "Schieferstraße"
    assert row.house_number == "20"
    assert row.postal_code == "06126"
    assert row.city == "Halle"

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = CustomerImportService(session).import_rows(preview.rows)
        assert result.customers_created == 1
        assert result.locations_created == 1
        customer = session.scalar(select(Customer).where(Customer.match_code == "COCABERL"))
        location = session.scalar(select(Location).where(Location.short_name == "COCAHALLE"))
        assert customer.name == "Coca-Cola,BerlinKDFG"
        assert location.customer_id == customer.id
        assert location.location_type == LocationType.CUSTOMER
        assert location.city == "Halle"


def test_repeated_import_updates_location_instead_of_duplicating(tmp_path):
    path = _workbook(tmp_path, [[
        "Werk A", "WERKA", "Werk A\nTestweg 1\nD 76133 Karlsruhe", "HAUPT | Hauptkunde"
    ]])
    preview = build_preview(path)
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = CustomerImportService(session)
        service.import_rows(preview.rows)
        preview.rows[0].name = "Werk A aktualisiert"
        result = service.import_rows(preview.rows)
        assert result.locations_updated == 1
        assert session.query(Customer).count() == 1
        assert session.query(Location).count() == 1
        assert session.scalar(select(Location)).name == "Werk A aktualisiert"


def test_same_location_match_code_with_different_addresses_creates_two_locations(tmp_path):
    path = _workbook(tmp_path, [
        ["Coca-Cola, Lüneburg", "COCALÜNEBURG", "Werk 1\nGoseburgstr. 25-39\nD 21339 Lüneburg", "COCABERL | Coca-Cola"],
        ["Coca-Cola, Lüneburg", "COCALÜNEBURG", "Werk 2\nBoecklerstr. 10\nD 21339 Lüneburg", "COCABERL | Coca-Cola"],
    ])
    preview = build_preview(path)
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = CustomerImportService(session).import_rows(preview.rows)
        assert result.customers_created == 1
        assert result.locations_created == 2
        locations = session.scalars(select(Location).order_by(Location.street)).all()
        assert [location.street for location in locations] == ["Boecklerstr.", "Goseburgstr."]
        assert locations[0].customer_id == locations[1].customer_id


def test_row_without_separate_main_customer_becomes_customer_and_location(tmp_path):
    path = _workbook(tmp_path, [[
        "CCEP DE MÖRFELDEN-WALLDORF", "COCAMÖRFEL17",
        "CCEP DE MÖRFELDEN-WALLDORF\nAN DER BRÜCKE 13-17\nD 64546 MÖRFELDEN-WALLDORF",
        "COCAMÖRFEL17 | CCEP DE MÖRFELDEN-WALLDORF",
    ]])
    preview = build_preview(path)
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = CustomerImportService(session).import_rows(preview.rows)
        customer = session.scalar(select(Customer))
        location = session.scalar(select(Location))
        assert result.customers_created == 1
        assert result.locations_created == 1
        assert customer.city == "MÖRFELDEN-WALLDORF"
        assert location.customer_id == customer.id


def test_existing_customer_with_same_name_is_reused(tmp_path):
    path = _workbook(tmp_path, [[
        "Anona Werk 3", "ANONA WERK3", "Anona GmbH\nFürther Eule 6\nD 04680 Colditz",
        "ANONA | Anona GmbH",
    ]])
    preview = build_preview(path)
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        existing = Customer(name="Anona GmbH", match_code="ANONA ALT", city="Colditz")
        session.add(existing); session.commit()
        result = CustomerImportService(session).import_rows(preview.rows)
        assert result.customers_created == 0
        assert session.query(Customer).count() == 1
        assert session.query(Location).count() == 1
        assert existing.match_code == "ANONA"
