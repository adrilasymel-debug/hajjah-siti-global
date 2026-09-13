import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['ENVIRONMENT']='test'
import pytest
from uuid import uuid4
from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base,get_db
from app.main import app
from app.models import Role,User
from app.security import hash_password,BOSS_PERMISSIONS,STAFF_PERMISSIONS
from app.config import settings

@pytest.fixture()
def ctx(tmp_path):
    test_url=os.environ.get('TEST_DATABASE_URL')
    admin=None;schema=None
    if test_url:
        schema='test_'+uuid4().hex
        admin=create_engine(test_url)
        with admin.begin() as connection:connection.execute(text('CREATE SCHEMA '+schema))
        engine=create_engine(test_url,connect_args={'options':'-csearch_path='+schema})
    else:
        engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        @event.listens_for(engine,'connect')
        def fk(c,_):c.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    settings.storage_path=tmp_path
    with factory() as db:
        db.add_all([Role(name='BOSS',permissions=BOSS_PERMISSIONS),Role(name='STAFF',permissions=STAFF_PERMISSIONS)]);db.flush()
        for name,role in [('boss','BOSS'),('staff','STAFF'),('other','STAFF')]:db.add(User(name=name,email=name+'@test.local',role=role,password_hash=hash_password('testing-password-123')))
        db.commit()
    def dependency():
        with factory() as db:
            try:yield db;db.commit()
            except Exception:db.rollback();raise
    app.dependency_overrides[get_db]=dependency
    clients={}
    for name in ['boss','staff','other']:
        client=TestClient(app);r=client.post('/api/auth/login',json={'email':name+'@test.local','password':'testing-password-123'});assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf'];clients[name]=client
    yield {**clients,'db':factory}
    app.dependency_overrides.clear();engine.dispose()
    if admin:
        with admin.begin() as connection:connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()
