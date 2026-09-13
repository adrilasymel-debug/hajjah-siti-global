import os
import subprocess
import sys
from datetime import datetime
from sqlalchemy import create_engine,text
from sqlalchemy.exc import DatabaseError
import pytest

def test_upgrade_preserves_payments_and_audit_is_append_only(tmp_path):
    url='sqlite:///'+str(tmp_path/'migrations.db').replace('\\','/')
    env={**os.environ,'DATABASE_URL':url,'ENVIRONMENT':'test'}
    def migrate(target):
        result=subprocess.run([sys.executable,'-m','alembic','upgrade',target],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    migrate('2c02fbe8132c');engine=create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO roles(name,permissions) VALUES ('BOSS','[]')"))
        db.execute(text("INSERT INTO users(id,created_at,name,email,password_hash,role,active) VALUES ('u',CURRENT_TIMESTAMP,'Owner','owner@example.test','hashed','BOSS',1)"))
        db.execute(text("INSERT INTO suppliers(id,created_at,updated_at,name,registration,contact,email,phone,address,payment_terms,active,notes) VALUES ('s',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'Supplier','','','','','',30,1,'')"))
        db.execute(text("INSERT INTO payments(id,created_at,supplier_id,payment_date,reference,method,notes,created_by,idempotency_key) VALUES ('p',CURRENT_TIMESTAMP,'s','2026-01-01','old reference','bank_transfer','','u','old-payment-key')"))
    migrate('head')
    with engine.begin() as db:
        payment=db.execute(text("SELECT reference,voided_at,void_reason FROM payments WHERE id='p'")).one()
        assert tuple(payment)==('old reference',None,'')
        db.execute(text("INSERT INTO audit_logs(id,created_at,actor_id,actor_name,action,entity,entity_id,details) VALUES ('a',CURRENT_TIMESTAMP,'u','Owner','test','payment','p','{}')"))
    for sql in ["UPDATE audit_logs SET action='changed' WHERE id='a'","DELETE FROM audit_logs WHERE id='a'"]:
        with pytest.raises(DatabaseError):
            with engine.begin() as db:db.execute(text(sql))
    engine.dispose()
