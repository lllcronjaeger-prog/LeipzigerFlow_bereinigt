from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from leipzigerflow.database.base import Base
from leipzigerflow.models import *
from leipzigerflow.models.dispatch_group import DispatchGroup, DispatchGroupRule
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.trailer import Trailer
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.contractor import Contractor


def test_dispatch_group_supports_multiple_resource_assignments():
    engine=create_engine('sqlite+pysqlite:///:memory:'); Base.metadata.create_all(engine)
    with Session(engine) as s:
        v=Vehicle(vehicle_number='1',license_plate='KA-LL 1')
        t=Trailer(trailer_number='T1',license_plate='KA-AB 1',trailer_type='Plane')
        d=Driver(match_code='D1',first_name='Max',last_name='Test')
        c=Contractor(match_code='LLL',name='Leipziger Logistik')
        g=DispatchGroup(name='Südwest',vehicles=[v],trailers=[t],drivers=[d],contractors=[c],rules=[DispatchGroupRule(entity_type='Fahrzeug',field_name='Kennzeichen',operator='enthält',comparison_value='KA')])
        s.add(g); s.commit(); s.expire_all()
        loaded=s.scalar(select(DispatchGroup).where(DispatchGroup.name=='Südwest'))
        assert [x.license_plate for x in loaded.vehicles]==['KA-LL 1']
        assert [x.trailer_number for x in loaded.trailers]==['T1']
        assert [x.match_code for x in loaded.drivers]==['D1']
        assert [x.match_code for x in loaded.contractors]==['LLL']
        assert loaded.rules[0].comparison_value=='KA'
