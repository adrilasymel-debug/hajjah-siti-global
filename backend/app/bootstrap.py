"""Create the first production owner interactively, after migrations."""
import getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import Role,User
from .security import BOSS_PERMISSIONS,STAFF_PERMISSIONS,hash_password,audit
from .schemas import UserIn

def main():
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role=='BOSS')):raise SystemExit('An owner already exists. Use User Management to add accounts.')
        data=UserIn(name=input('Owner name: '),email=input('Owner email: '),password=getpass.getpass('Password (12+ characters): '),role='BOSS')
        db.merge(Role(name='BOSS',permissions=BOSS_PERMISSIONS));db.merge(Role(name='STAFF',permissions=STAFF_PERMISSIONS));db.flush()
        user=User(name=data.name,email=data.email.lower(),role='BOSS',password_hash=hash_password(data.password));db.add(user);db.flush();audit(db,user,'initial_owner_created','user',user.id);db.commit();print('Owner created.')

if __name__=='__main__':main()
