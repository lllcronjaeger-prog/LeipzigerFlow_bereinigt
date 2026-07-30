from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.imports.customer_excel import build_preview
from leipzigerflow.models.customer import Customer
from leipzigerflow.services.customer_import_service import CustomerImportService


def test_customer_import_parses_address_and_links_freight_payer(tmp_path):
    path = tmp_path / "kunden.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(["Name", "Matchcode", "Anschrift", "Hauptkunde"])
    ws.append(["Coca-Cola, Halle", "COCAHALLE", "Coca Cola\nSchieferstraße 20\nD 06126 Halle", "COCABERL | Coca-Cola,BerlinKDFG"])
    wb.save(path)

    preview = build_preview(path)
    row = preview.rows[0]
    assert row.street == "Schieferstraße"
    assert row.house_number == "20"
    assert row.postal_code == "06126"
    assert row.city == "Halle"
    assert row.freight_payer_match_code == "COCABERL"

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = CustomerImportService(session)
        result = service.import_rows(preview.rows)
        assert result.created == 1
        assert result.freight_payers_created == 1
        customer = session.scalar(select(Customer).where(Customer.match_code == "COCAHALLE"))
        assert customer.freight_payer.match_code == "COCABERL"


def test_repeated_customer_import_updates_instead_of_duplicating(tmp_path):
    path = tmp_path / "kunden.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(["Name", "Matchcode", "Anschrift", "Hauptkunde"])
    ws.append(["Kunde A", "A1", "Kunde A\nTestweg 1\nD 76133 Karlsruhe", "HAUPT | Hauptkunde"])
    wb.save(path)
    preview = build_preview(path)
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = CustomerImportService(session)
        service.import_rows(preview.rows)
        preview.rows[0].city = "Ettlingen"
        result = service.import_rows(preview.rows)
        assert result.updated == 1
        assert session.query(Customer).filter(Customer.match_code == "A1").count() == 1
