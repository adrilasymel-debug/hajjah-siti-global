import secrets
import bcrypt
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session as DBSession
from .db import get_db
from .config import settings
from .models import User, Session, Role, LoginAttempt, now
from .security import current_user, digest, audit, hash_password
from .schemas import LoginIn, PasswordIn

router = APIRouter(prefix='/auth', tags=['Authentication'])
_dummy = bcrypt.hashpw(b'invalid-password', bcrypt.gensalt())

@router.post('/login')
def login(data: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    if request.headers.get('origin') and request.headers['origin'] != settings.frontend_origin:
        raise HTTPException(403, 'Untrusted origin')
    cutoff = now() - timedelta(minutes=15)
    key = digest(data.email.lower())
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    if db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key==key, LoginAttempt.created_at>=cutoff)) >= 8:
        raise HTTPException(429, 'Too many sign-in attempts. Try again in 15 minutes.')
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    encoded = data.password.encode()
    valid = bcrypt.checkpw(encoded if len(encoded)<=72 else b'invalid', user.password_hash.encode() if user else _dummy)
    if not user or not user.active or not valid:
        db.add(LoginAttempt(key=key)); db.commit()
        raise HTTPException(401, 'Email or password is incorrect')
    db.execute(delete(LoginAttempt).where(LoginAttempt.key==key))
    db.execute(delete(Session).where(Session.expires_at<now()))
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token), csrf=csrf, user_id=user.id, expires_at=now()+timedelta(hours=settings.session_hours)))
    audit(db,user,'login','user',user.id)
    response.set_cookie('fo_session',token,httponly=True,secure=settings.environment=='production',samesite='lax',max_age=settings.session_hours*3600,path='/')
    return {'user': {'id':user.id,'name':user.name,'role':user.role,'email':user.email}, 'csrf':csrf, 'permissions':db.get(Role,user.role).permissions}

@router.get('/me')
def me(request: Request, user=Depends(current_user), db: DBSession=Depends(get_db)):
    return {'user': {'id':user.id,'name':user.name,'role':user.role,'email':user.email},'csrf':request.state.session.csrf,'permissions':request.state.permissions}

@router.post('/logout')
def logout(request: Request,response: Response,user=Depends(current_user),db: DBSession=Depends(get_db)):
    db.delete(request.state.session); audit(db,user,'logout','user',user.id)
    response.delete_cookie('fo_session',path='/')
    return {'message':'Signed out'}

@router.post('/password')
def change_password(data:PasswordIn,request:Request,user=Depends(current_user),db:DBSession=Depends(get_db)):
    if len(data.current_password.encode())>72 or not bcrypt.checkpw(data.current_password.encode(),user.password_hash.encode()):
        raise HTTPException(422,'Current password is incorrect')
    user.password_hash=hash_password(data.new_password)
    db.execute(delete(Session).where(Session.user_id==user.id,Session.id!=request.state.session.id))
    audit(db,user,'password_changed','user',user.id)
    return {'message':'Password updated. Other sessions have been signed out.'}
