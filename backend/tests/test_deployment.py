import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import User,BusinessSetting
from app import launch,backup
from app.config import settings

def test_first_owner_bootstrap_is_empty_and_idempotent(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'bootstrap.db'))
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    monkeypatch.setattr(launch,'SessionLocal',factory)
    monkeypatch.setattr(launch.command,'upgrade',lambda *args:None)
    monkeypatch.setenv('INITIAL_OWNER_NAME','Business Owner')
    monkeypatch.setenv('INITIAL_OWNER_EMAIL','owner@example.com')
    monkeypatch.setenv('INITIAL_OWNER_PASSWORD','private-test-password')
    launch.setup()
    monkeypatch.delenv('INITIAL_OWNER_PASSWORD')
    launch.setup()
    with factory() as db:
        users=list(db.scalars(select(User)))
        assert len(users)==1 and users[0].role=='BOSS'
        assert users[0].password_hash!='private-test-password'
        assert db.get(BusinessSetting,'company_name').value==settings.company_name
    engine.dispose()

def test_backup_rejects_hash_mismatch_and_preserves_originals(ctx,tmp_path,monkeypatch):
    from io import BytesIO
    from PIL import Image
    image=BytesIO();Image.new('RGB',(80,80),'white').save(image,'PNG')
    r=ctx['staff'].post('/api/supplier-bills/upload',files={'file':('invoice.png',image.getvalue(),'image/png')})
    assert r.status_code==201
    monkeypatch.setattr(settings,'database_url','postgresql+psycopg://user:password@example.com/database')
    monkeypatch.setattr(backup,'SessionLocal',ctx['db'])
    monkeypatch.setattr(backup.shutil,'which',lambda name:'pg_dump')
    def fake_dump(command,**kwargs):
        assert 'password' not in ' '.join(command)
        Path(command[command.index('--file')+1]).write_bytes(b'test dump')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(backup.subprocess,'run',fake_dump)
    folder=backup.backup(tmp_path/'complete-backup')
    manifest=json.loads((folder/'manifest.json').read_text())
    assert manifest['complete'] and len(manifest['documents'])==1
    assert (folder/'objects'/manifest['documents'][0]['key']).read_bytes()==image.getvalue()
    monkeypatch.setattr(backup.storage,'get',lambda key:b'corrupted bytes')
    with pytest.raises(RuntimeError,match='hash differs'):backup.backup(tmp_path/'bad-backup')
    assert not list((tmp_path/'bad-backup').rglob('manifest.json'))
