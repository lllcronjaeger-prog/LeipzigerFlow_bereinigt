from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from leipzigerflow.database.base import Base
from leipzigerflow.models.audit import AuditLog
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.models.location_type import LocationType
from leipzigerflow.models.warehouse import WarehouseGroup
from leipzigerflow.services.audit_context import set_user


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_audit_records_user_and_changed_field():
    session = make_session()
    set_user(7, "dispo", "Disposition")
    customer = Customer(name="Testkunde", short_name="TEST", active=True)
    session.add(customer)
    session.commit()
    customer.short_name = "NEU"
    session.commit()
    entries = list(session.scalars(select(AuditLog).where(AuditLog.entity_type == "Customer")))
    assert any(entry.action == "Angelegt" and entry.username == "dispo" for entry in entries)
    assert any(entry.action == "Geändert" and entry.field_name == "short_name" for entry in entries)


def test_warehouse_group_supplies_weekday_hours():
    session = make_session()
    group = WarehouseGroup(name="LIDL", monday_hours="06:00-13:00")
    warehouse = Location(
        location_type=LocationType.WAREHOUSE,
        name="LIDL Karlsruhe",
        city="Karlsruhe",
        warehouse_group=group,
    )
    session.add(warehouse)
    session.commit()
    assert warehouse.warehouse_group.hours_for_weekday(0) == "06:00-13:00"
