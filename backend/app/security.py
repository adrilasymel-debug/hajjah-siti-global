import hashlib
import secrets
from datetime import timedelta, timezone
import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from .db import get_db
from .models import User, Role, Session, Audit, now

STAFF_PERMISSIONS = ['bills.read_own', 'bills.create', 'bills.edit_own', 'bills.verify_own', 'documents.read_own']
BOSS_PERMISSIONS = STAFF_PERMISSIONS + ['dashboard.read', 'bills.read_all', 'bills.manage', 'suppliers.manage', 'payments.manage', 'employees.manage', 'payroll.manage', 'reports.read', 'audit.read', 'users.manage', 'settings.manage', 'documents.manage', 'expected.manage']

def hash_password(password):
    if len(password.encode()) > 72:
        raise HTTPException(422, 'Password must be at most 72 UTF-8 bytes')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def audit(db, user, action, entity, entity_id, details=None):
    from uuid import uuid4
    from .email_delivery import enqueue
    event=Audit(id=str(uuid4()),actor_id=user.id if user else None, actor_name=user.name if user else 'Processing service',
                action=action, entity=entity, entity_id=entity_id, details=details or {})
    db.add(event)
    enqueue(db,event)

def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get('fo_session', '')
    session = db.scalar(select(Session).where(Session.token_hash == digest(token))) if token else None
    if not session or session.expires_at.replace(tzinfo=timezone.utc) < now():
        raise HTTPException(401, 'Please sign in to continue')
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, 'Your account is unavailable')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf):
            raise HTTPException(403, 'Your session needs refreshing. Reload and try again.')
    request.state.session = session
    request.state.permissions = db.get(Role, user.role).permissions
    return user

def require(permission):
    def dependency(request: Request, user: User = Depends(current_user)):
        if permission not in request.state.permissions:
            raise HTTPException(403, 'You do not have permission to access this area')
        return user
    return dependency

def can_read_bill(db, user, bill):
    if not bill or (user.role != 'BOSS' and (bill.submitted_by != user.id or bill.archived_at is not None)):
        raise HTTPException(404, 'Invoice not found')
    return bill
