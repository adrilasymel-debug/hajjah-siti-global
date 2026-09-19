import httpx
import pytest
from sqlalchemy import select
from app import email_delivery as mail
from app.models import EmailDelivery, Bill, User
from app.security import audit

@pytest.fixture
def enabled(ctx,monkeypatch):
    monkeypatch.setattr(mail.settings,'email_enabled',True)
    monkeypatch.setattr(mail.settings,'email_free_tier_confirmed',True)
    monkeypatch.setattr(mail.settings,'email_from','sender@example.com')
    monkeypatch.setattr(mail.settings,'brevo_api_key','test-secret')
    monkeypatch.setattr(mail,'SessionLocal',ctx['db'])
    return ctx

def event(ctx,action='invoice_uploaded'):
    with ctx['db']() as db:
        user=db.scalar(select(User).where(User.name=='staff'))
        bill=Bill(submitted_by=user.id);db.add(bill);db.flush()
        audit(db,user,action,'bill',bill.id);db.commit()

def test_email_queued_atomically_and_sent_to_owner(enabled,monkeypatch):
    event(enabled);calls=[]
    def send(url,**kwargs):calls.append(kwargs['json']);return httpx.Response(201)
    monkeypatch.setattr(mail.httpx,'post',send)
    assert mail.run_once()
    assert calls[0]['to'][0]['email']=='boss@test.local'
    assert '/bills/' in calls[0]['textContent']
    assert mail.run_once() is False
    assert enabled['boss'].get('/api/email-deliveries').json()['counts']['sent']==1
    assert enabled['staff'].get('/api/email-deliveries').status_code==403

def test_rollback_does_not_send(enabled):
    with enabled['db']() as db:
        user=db.scalar(select(User).where(User.name=='staff'));bill=Bill(submitted_by=user.id);db.add(bill);db.flush()
        audit(db,user,'invoice_uploaded','bill',bill.id);db.rollback()
    assert mail.run_once() is False

def test_processing_email_to_submitter(enabled,monkeypatch):
    event(enabled,'invoice_processed');calls=[]
    monkeypatch.setattr(mail.httpx,'post',lambda url,**kwargs:(calls.append(kwargs['json']) or httpx.Response(201)))
    mail.run_once();assert calls[0]['to'][0]['email']=='staff@test.local'

@pytest.mark.parametrize('code,status',[(429,'queued'),(503,'queued'),(401,'failed')])
def test_delivery_errors_preserve_record(enabled,monkeypatch,code,status):
    event(enabled)
    monkeypatch.setattr(mail.httpx,'post',lambda *a,**kw:httpx.Response(code,text='sensitive provider response'))
    assert mail.run_once()
    with enabled['db']() as db:
        r=db.scalar(select(EmailDelivery));assert r.status==status;assert 'sensitive' not in r.last_error
        assert db.scalar(select(Bill)) is not None

def test_disabled_and_inactive_recipient(enabled,monkeypatch):
    event(enabled)
    monkeypatch.setattr(mail.settings,'email_enabled',False)
    assert mail.run_once() is False
    monkeypatch.setattr(mail.settings,'email_enabled',True)
    with enabled['db']() as db:
        user=db.scalar(select(User).where(User.name=='boss'));user.active=False;db.commit()
    monkeypatch.setattr(mail.httpx,'post',lambda *a,**kw:pytest.fail('Must not send to inactive user'))
    mail.run_once()
    with enabled['db']() as db:assert db.scalar(select(EmailDelivery)).status=='cancelled'

def test_wastage_events_notify_correct_people(enabled):
    from tests.test_wastage import report,instruct,proof
    row=report(enabled).json()
    row=instruct(enabled,row).json()
    assert proof(enabled,row).status_code==200
    with enabled['db']() as db:
        deliveries=list(db.execute(select(EmailDelivery.subject,User.name).join(User,User.id==EmailDelivery.user_id)).all())
    assert sorted(deliveries)==sorted([
        ('New wastage report submitted','boss'),
        ('Wastage action required','staff'),
        ('Wastage proof ready for review','boss')])

def test_free_tier_confirmation_blocks_sending(enabled,monkeypatch):
    event(enabled)
    monkeypatch.setattr(mail.settings,'free_only',True)
    monkeypatch.setattr(mail.settings,'email_free_tier_confirmed',False)
    monkeypatch.setattr(mail.httpx,'post',lambda *a,**kw:pytest.fail('Free tier must be confirmed'))
    assert mail.run_once() is False
