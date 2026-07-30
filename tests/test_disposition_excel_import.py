from datetime import date, time
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.imports.disposition_excel import build_preview, parse_address, parse_time_window
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.services.disposition_import_service import DispositionImportService


def make_file(path: Path):
    wb = Workbook(); ws = wb.active; ws.title = "Disposition"
    ws.append(["Ladetermin : 30.07.2026"])
    ws.append(["Dossier", "Ladetermin", "Liefertermin", "Transportnummer", "Kundenauftragsnummer", "Beladeadresse", "Entladeadresse", "Fahrzeug", "Ladetermin - Zeitfenster", "Liefertermin - Zeitfenster", "Frachtzahler", "Fahrer", "Stellplätze", "Paletten", "frachtpfl. Gewicht"])
    ws.append(["D1", "30.07.2026", "31.07.2026", "T100", "K100", "Lager A\nD 76149 Karlsruhe", "Kunde B\nD 68159 Mannheim", "KA-LL 8043", "08:00 - 09:00", "12:00 - 13:00", "Coca-Cola,BerlinKDFG", "Max Mustermann", 13.2, "EUR: 33", 22000])
    wb.save(path)


def test_parser_reads_disposition(tmp_path):
    path = tmp_path / "disp.xlsx"; make_file(path)
    preview = build_preview(path)
    assert len(preview.rows) == 1
    row = preview.rows[0]
    assert row.transport_number == "T100"
    assert row.loading_date == date(2026, 7, 30)
    assert row.loading_time_from == time(8, 0)
    assert row.pallets == 33
    assert row.has_planning


def test_address_and_time_parser():
    address = parse_address("LIT Lager\nD 76726 Germersheim")
    assert address.name == "LIT Lager"
    assert address.postal_code == "76726"
    assert parse_time_window("06:00 - 20:30") == (time(6, 0), time(20, 30))


def test_repeated_import_updates_without_duplicates(tmp_path):
    path = tmp_path / "disp.xlsx"; make_file(path)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = DispositionImportService(session)
        first = service.import_rows(build_preview(path).rows)
        second = service.import_rows(build_preview(path).rows)
        assert first.orders_created == 1
        assert second.orders_updated == 1
        assert len(session.scalars(select(TransportOrder)).all()) == 1
        assert len(session.scalars(select(Location)).all()) == 2
        assert len(session.scalars(select(Customer)).all()) == 1
        assert len(session.scalars(select(Tour)).all()) == 1
