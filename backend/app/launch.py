"""Free single-service deployment: migrations, optional first owner, API and inline worker."""
import os
from alembic.config import Config
from alembic import command
from sqlalchemy import select
from .db import SessionLocal
from .models import User,Role,BusinessSetting
from .security import hash_password,BOSS_PERMISSIONS,STAFF_PERMISSIONS,audit
from .schemas import UserIn
from .config import settings

def setup():
    command.upgrade(Config('alembic.ini'),'head')
    with SessionLocal() as db:
        if not db.scalar(select(User.id)):
            password=os.environ.get('INITIAL_OWNER_PASSWORD','')
            if not password:raise RuntimeError('Set INITIAL_OWNER_NAME, INITIAL_OWNER_EMAIL and INITIAL_OWNER_PASSWORD in your hosting secrets to create the first owner')
            data=UserIn(name=os.environ.get('INITIAL_OWNER_NAME',''),email=os.environ.get('INITIAL_OWNER_EMAIL',''),password=password,role='BOSS')
            db.add_all([Role(name='BOSS',permissions=BOSS_PERMISSIONS),Role(name='STAFF',permissions=STAFF_PERMISSIONS)]);db.flush()
            user=User(name=data.name,email=data.email.lower(),role=data.role,password_hash=hash_password(data.password));db.add(user);db.flush()
            audit(db,user,'initial_owner_created','user',user.id)
            db.add(BusinessSetting(key='company_name',value=settings.company_name));db.commit()

if __name__=='__main__':
    setup()
    import uvicorn
    uvicorn.run('app.main:app',host='0.0.0.0',port=int(os.environ.get('PORT','10000')),workers=1,proxy_headers=True)
