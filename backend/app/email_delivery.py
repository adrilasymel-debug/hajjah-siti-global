"""Transactional outbox: external delivery never runs inside a submission request."""
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from .config import settings
from .db import SessionLocal, get_db
from .models import Audit, Bill, Wastage, User, EmailDelivery, now

# Short, fixed subjects avoid exposing invoice values or damage details in email.
EVENTS = {
    'invoice_uploaded': ('New invoice submitted', 'boss'),
    'invoice_created': ('New invoice submitted', 'boss'),
    'invoice_verified': ('Invoice verified and ready for approval', 'boss'),
    'invoice_processed': ('Invoice ready for your review', 'staff'),
    'invoice_processing_failed': ('Invoice needs manual review', 'staff'),
    'invoice_rejected': ('Invoice requires your attention', 'staff'),
    'invoice_approved': ('Invoice approved', 'staff'),
    'wastage_reported': ('New wastage report submitted', 'boss'),
    'wastage_instructed': ('Wastage action required', 'staff'),
    'wastage_proof_submitted': ('Wastage proof ready for review', 'boss'),
    'wastage_more_proof_requested': ('More wastage evidence required', 'staff'),
    'wastage_completed': ('Wastage case completed', 'staff'),
}

def configured():
    return bool(settings.email_enabled and settings.brevo_api_key and settings.email_from
                and (not settings.free_only or settings.email_free_tier_confirmed))

def enqueue(db, event):
    if not settings.email_enabled or event.action not in EVENTS: return
    subject, audience = EVENTS[event.action]
    if event.entity not in ['bill','wastage']: return
    record = db.get(Bill if event.entity=='bill' else Wastage,event.entity_id)
    if not record: return
    query=select(User).where(User.active==True)
    query=query.where(User.role=='BOSS') if audience=='boss' else query.where(User.id==record.submitted_by)
    for user in db.scalars(query):
        db.add(EmailDelivery(user_id=user.id,event_id=event.id,subject=subject,
                             path=('/bills/' if event.entity=='bill' else '/wastage/')+record.id))

def run_once():
    if not configured(): return False
    # Keep the row lock until the bounded HTTP call completes. Concurrent workers
    # skip it; a crashed worker releases the transaction for retry.
    with SessionLocal() as db:
        row=db.scalar(select(EmailDelivery).where(EmailDelivery.status=='queued',EmailDelivery.available_at<=now()).order_by(EmailDelivery.created_at).with_for_update(skip_locked=True).limit(1))
        if not row:return False
        user=db.get(User,row.user_id)
        event=db.get(Audit,row.event_id)
        record=db.get(Bill if event.entity=='bill' else Wastage,event.entity_id)
        audience=EVENTS[event.action][1]
        if not user or not user.active or not record or (audience=='boss' and user.role!='BOSS') or (audience=='staff' and user.id!=record.submitted_by):
            row.status='cancelled';db.commit();return True
        row.attempts+=1
        link=settings.frontend_origin.rstrip('/')+row.path
        try:
            response=httpx.post('https://api.brevo.com/v3/smtp/email',headers={'api-key':settings.brevo_api_key},json={
                'sender':{'name':settings.company_name,'email':settings.email_from},
                'to':[{'email':user.email,'name':user.name}],
                'subject':settings.company_name+' — '+row.subject,
                'textContent':row.subject+'\n\nSign in to review the record and any required action:\n'+link+'\n\nPrivate documents and photos are available only after signing in.',
            },timeout=15)
            if response.status_code==201:
                row.status='sent';row.sent_at=now();row.last_error=''
            elif response.status_code==429:
                # Free quota exhausted: wait rather than buying credits or dropping the message.
                row.attempts-=1;row.available_at=now()+timedelta(hours=1);row.last_error='Provider quota reached; waiting to retry'
            elif response.status_code==401:
                row.status='failed';row.last_error='Brevo 401: API key invalid or inactive. Use an active API key, not an SMTP key.'
            elif response.status_code==403:
                row.status='failed';row.last_error='Brevo 403: account is not permitted to send. Check transactional activation and API access.'
            elif response.status_code>=500:
                retry(row,'Email provider temporarily unavailable')
            else:
                row.status='failed';row.last_error='Email provider rejected the message; check the sender and recipient'
        except httpx.HTTPError:
            retry(row,'Email connection interrupted; waiting to retry')
        db.commit();return True

def retry(row,message):
    row.last_error=message
    row.status='failed' if row.attempts>=5 else 'queued'
    row.available_at=now()+timedelta(minutes=min(60,2**row.attempts))

# Owner-only delivery status; never return provider credentials or email bodies.
from .security import require
router=APIRouter(tags=['Email notifications'])

@router.get('/email-deliveries')
def status(user=Depends(require('settings.manage')),db=Depends(get_db)):
    counts=dict(db.execute(select(EmailDelivery.status,func.count()).group_by(EmailDelivery.status)).all())
    failures=list(db.scalars(select(EmailDelivery).where(EmailDelivery.status=='failed').order_by(EmailDelivery.created_at.desc()).limit(20)))
    return {'enabled':settings.email_enabled,'configured':configured(),'counts':counts,
            'failures':[{'id':r.id,'subject':r.subject,'error':r.last_error} for r in failures]}

@router.post('/email-deliveries/retry')
def retry_failed(user=Depends(require('settings.manage')),db=Depends(get_db)):
    rows=list(db.scalars(select(EmailDelivery).where(EmailDelivery.status=='failed').with_for_update(skip_locked=True).limit(100)))
    for row in rows:row.status='queued';row.attempts=0;row.available_at=now()
    return {'queued':len(rows)}

@router.post('/email-deliveries/{delivery_id}/retry')
def retry_one(delivery_id: str,user=Depends(require('settings.manage')),db=Depends(get_db)):
    row=db.scalar(select(EmailDelivery).where(EmailDelivery.id==delivery_id,EmailDelivery.status=='failed').with_for_update())
    if not row:raise HTTPException(404,'Failed email not found')
    row.status='queued';row.attempts=0;row.available_at=now()
    return {'queued':1}
