from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leipzigerflow.database.base import Base
from leipzigerflow.imports.vehicle_excel import (
    assign_match_codes,
    build_preview,
    is_vehicle_plate,
    normalize_license_plate,
    FleetImportRow,
)
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.services.vehicle_import_service import VehicleImportService


def _write_sample(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Unternehmer", "Kennzeichen KfZ", "Typ"])
    sheet.append(["LLL SW", "KA-LL 8043", "Sattelzugmaschine"])
    sheet.append(["LLL SW", "FR-H 4209", "Trailer"])
    sheet.append(["LLL SW", "KA-ET 8043", "Trailer"])
    sheet.append(["LLL SW", "OFFEN", ""])
    workbook.save(path)


def test_plate_normalization_and_vehicle_rule():
    assert normalize_license_plate(" ka ll 8043 ") == "KA LL 8043"
    assert normalize_license_plate("L-LL8068") == "L-LL 8068"
    assert is_vehicle_plate("KA-LL 8043")
    assert is_vehicle_plate("KA LL 8043")
    assert not is_vehicle_plate("L-LL 8043")
    assert not is_vehicle_plate("KA-ET 8043")


def test_match_code_uses_number_and_prefix_on_collision():
    rows = [
        FleetImportRow(2, "KA-LL 8043", "Zugmaschine"),
        FleetImportRow(3, "FR-H 4209", "Trailer"),
        FleetImportRow(4, "KA-ET 8043", "Trailer"),
    ]
    assign_match_codes(rows)
    assert rows[0].match_code == "8043"
    assert rows[1].match_code == "4209"
    assert rows[2].match_code == "E8043"


def test_preview_reads_only_plate_column_and_marks_placeholders(tmp_path):
    path = tmp_path / "fahrzeuge.xlsx"
    _write_sample(path)
    preview = build_preview(path)
    assert len(preview.rows) == 4
    assert preview.rows[0].resource_type == "Zugmaschine"
    assert preview.rows[0].match_code == "8043"
    assert preview.rows[1].resource_type == "Trailer"
    assert preview.rows[1].match_code == "4209"
    assert preview.rows[2].match_code == "E8043"
    assert preview.rows[3].status == "Fehler"
    assert "Kein gültiges Kfz-Kennzeichen" in preview.rows[3].errors


def test_import_creates_and_updates_vehicles_and_trailers(tmp_path):
    path = tmp_path / "fahrzeuge.xlsx"
    _write_sample(path)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = VehicleImportService(session)
        preview = service.mark_existing(build_preview(path))
        result = service.import_rows(preview.rows)
        assert result.vehicles_created == 1
        assert result.trailers_created == 2
        assert result.skipped == 1

        vehicle = session.scalar(select(Vehicle))
        assert vehicle is not None
        assert vehicle.vehicle_number == "8043"
        assert vehicle.license_plate == "KA-LL 8043"
        assert vehicle.active

        trailers = list(session.scalars(select(Trailer).order_by(Trailer.trailer_number)))
        assert {trailer.trailer_number for trailer in trailers} == {"4209", "E8043"}
        assert all(trailer.active for trailer in trailers)

        preview = service.mark_existing(build_preview(path))
        assert preview.rows[0].status == "Update"
        result = service.import_rows(preview.rows)
        assert result.vehicles_updated == 1
        assert result.trailers_updated == 2
