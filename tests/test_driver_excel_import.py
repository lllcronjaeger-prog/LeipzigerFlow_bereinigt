from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.imports.driver_excel import build_preview, parse_address, parse_contact
from leipzigerflow.models.driver import Driver
from leipzigerflow.services.driver_import_service import DriverImportService


def test_parse_dispo_address():
    parsed = parse_address("Ladislav Hangonyi\nNeckarstr. 17\nD 76437 Rastatt")
    assert parsed == {
        "first_name": "Ladislav",
        "last_name": "Hangonyi",
        "street": "Neckarstr.",
        "house_number": "17",
        "postal_code": "76437",
        "city": "Rastatt",
        "country": "Deutschland",
    }


def test_parse_long_name_and_contact_fallback():
    parsed = parse_address("Muhammad Waqar Ul Hassan\nHauptstr. 5\n76133 Karlsruhe")
    assert parsed["first_name"] == "Muhammad"
    assert parsed["last_name"] == "Waqar Ul Hassan"
    phone, mobile, raw = parse_contact("", "Tel.: 0178 - 3440 614")
    assert phone == "0178 3440 614"
    assert mobile == ""
    assert raw == ""


def _write_sample(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["MatchCode", "Anschrift", "Kontakt", "LMK Führung", "Sonderberechtigungen"])
    ws.append(["hani", "Ladislav Hangonyi\nNeckarstr. 17\nD 76437 Rastatt", "07222/30571\n0178/3440604", "Nein", ""])
    ws.append(["fronc", "Arkadiusz Fronc\nMusterweg 2\nPL 70-001 Szczecin", "", "Nein", "Tel.: 0178 - 3440 614"])
    wb.save(path)


def test_preview_ignores_lmk_and_parses_rows(tmp_path):
    path = tmp_path / "fahrer.xlsx"
    _write_sample(path)
    preview = build_preview(path)
    assert len(preview.rows) == 2
    assert preview.rows[0].match_code == "hani"
    assert preview.rows[0].phone == "07222 30571"
    assert preview.rows[0].mobile == "0178 3440604"
    assert preview.rows[1].country == "Polen"
    assert preview.rows[1].phone == "0178 3440 614"
    assert all(row.is_valid for row in preview.rows)


def test_import_creates_and_updates_by_match_code(tmp_path):
    path = tmp_path / "fahrer.xlsx"
    _write_sample(path)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = DriverImportService(session)
        preview = service.mark_existing(build_preview(path))
        result = service.import_rows(preview.rows)
        assert result.created == 2
        drivers = list(session.scalars(select(Driver).order_by(Driver.match_code)))
        assert len(drivers) == 2
        assert all(driver.active for driver in drivers)
        assert drivers[0].import_source == "Dispoplan Excel"

        preview.rows[0].city = "Ettlingen"
        result = service.import_rows([preview.rows[0]])
        assert result.updated == 1
        assert session.scalar(select(Driver).where(Driver.match_code == "hani")).city == "Ettlingen"
