from datetime import date,timedelta
from io import BytesIO
from decimal import Decimal
from PIL import Image
from sqlalchemy import select
from app.models import Audit,User,Bill,Allocation

def supplier(ctx):
    r=ctx['boss'].post('/api/suppliers',json={'name':'Test Supply'});assert r.status_code==201,r.text;return r.json()['id']

def invoice(ctx,supplier_id=None,number='INV-001',who='staff'):
    sid=supplier_id or supplier(ctx)
    payload={'supplier_id':sid,'number':number,'invoice_date':str(date.today()-timedelta(days=40)),'due_date':str(date.today()-timedelta(days=10)),'subtotal':'100.00','tax':'6.00','total':'106.00','items':[{'description':'Materials','quantity':2,'unit_price':'50.00','tax':'6.00','total':'106.00'}]}
    r=ctx[who].post('/api/supplier-bills',json=payload);assert r.status_code==201,r.text;return r.json()

def verified(ctx):
    b=invoice(ctx);r=ctx['staff'].post('/api/supplier-bills/'+b['id']+'/verify',json={'version':b['version']});assert r.status_code==200,r.text;return r.json()

def payment(ctx,b,amount='40.00',key='unique-payment-key-1'):
    return ctx['boss'].post('/api/payments',json={'supplier_id':b['supplier_id'],'payment_date':str(date.today()),'reference':'TRF-001','method':'bank_transfer','idempotency_key':key,'allocations':[{'bill_id':b['id'],'amount':amount}]})

def test_authentication_logout_csrf(ctx):
    c=ctx['staff'];assert c.get('/api/auth/me').json()['user']['role']=='STAFF'
    old=c.headers.pop('X-CSRF-Token');assert c.post('/api/auth/logout').status_code==403
    c.headers['X-CSRF-Token']=old;assert c.post('/api/auth/logout').status_code==200;assert c.get('/api/auth/me').status_code==401
    assert c.post('/api/auth/login',json={'email':'staff@test.local','password':'wrong'}).status_code==401

def test_role_restrictions_and_ownership(ctx):
    for path in ['/employees','/payroll','/payslips','/users','/settings','/reports','/audit','/payments','/dashboard','/suppliers','/expected-invoices']:
        assert ctx['staff'].get('/api'+path).status_code==403,path
    b=invoice(ctx);assert ctx['other'].get('/api/supplier-bills/'+b['id']).status_code==404
    assert ctx['other'].post('/api/supplier-bills/'+b['id']+'/verify',json={'version':1}).status_code==404
    assert ctx['other'].get('/api/supplier-bills').json()['total']==0
    assert ctx['staff'].post('/api/suppliers',json={'name':'Forbidden'}).status_code==403

def test_invoice_verification_and_audit(ctx):
    b=verified(ctx);assert b['status']=='verified';assert b['verified_by'];assert b['verified_at'];assert Decimal(b['outstanding'])==106
    with ctx['db']() as db:
        event=db.scalar(select(Audit).where(Audit.action=='invoice_verified'));assert event.entity_id==b['id'];assert event.details['total']=='106.00'

def test_invoice_without_due_date_can_be_verified(ctx):
    response=ctx['staff'].post('/api/supplier-bills',json={
        'supplier_id':supplier(ctx),'number':'NO-DUE-001',
        'invoice_date':str(date.today()),'subtotal':'50.00','tax':'0','total':'50.00'})
    assert response.status_code==201,response.text
    bill=response.json()
    assert bill['due_date'] is None
    verified=ctx['staff'].post('/api/supplier-bills/'+bill['id']+'/verify',json={'version':bill['version']})
    assert verified.status_code==200,verified.text
    assert verified.json()['payment_status']=='unpaid'

def test_duplicate_requires_owner_resolution(ctx):
    first=verified(ctx);b=invoice(ctx,first['supplier_id']);assert first['id'] in b['duplicate_ids']
    assert ctx['staff'].post('/api/supplier-bills/'+b['id']+'/verify',json={'version':1}).status_code==409
    assert ctx['boss'].post('/api/supplier-bills/'+b['id']+'/verify',json={'version':1,'duplicate_resolution':'Supplier confirmed separate delivery with reused reference.'}).status_code==200

def test_payment_outstanding_overpayment_and_idempotency(ctx):
    b=verified(ctx);p=payment(ctx,b);assert p.status_code==201,p.text
    assert payment(ctx,b).json()['id']==p.json()['id']
    detail=ctx['boss'].get('/api/supplier-bills/'+b['id']).json();assert Decimal(detail['outstanding'])==66;assert detail['payment_status']=='overdue'
    assert payment(ctx,b,'67','another-payment-key').status_code==409
    assert payment(ctx,b,'66','final-payment-key').status_code==201
    assert ctx['boss'].get('/api/supplier-bills/'+b['id']).json()['payment_status']=='paid'
    assert Decimal(ctx['boss'].get('/api/dashboard').json()['outstanding'])==0
    assert Decimal(ctx['boss'].get('/api/suppliers').json()['items'][0]['outstanding'])==0

def test_totals_and_stale_edit_rejected(ctx):
    b=invoice(ctx);payload={k:b[k] for k in ['supplier_id','number','invoice_date','due_date','subtotal','tax','total','version']};payload['total']='107'
    r=ctx['staff'].put('/api/supplier-bills/'+b['id'],json=payload);assert r.status_code==200,r.text
    assert ctx['staff'].post('/api/supplier-bills/'+b['id']+'/verify',json={'version':2}).status_code==422
    assert ctx['staff'].put('/api/supplier-bills/'+b['id'],json=payload).status_code==409

def test_paid_invoice_locked(ctx):
    b=verified(ctx);payment(ctx,b)
    payload={k:b[k] for k in ['supplier_id','number','invoice_date','due_date','subtotal','tax','total','version']}
    assert ctx['boss'].put('/api/supplier-bills/'+b['id'],json=payload).status_code==409
    assert ctx['boss'].post('/api/supplier-bills/'+b['id']+'/reject',json={'reason':'Incorrect invoice'}).status_code==409

def test_payroll_calculations_and_payslip(ctx):
    c=ctx['boss'];e=c.post('/api/employees',json={'employee_code':'E1','name':'Test Employee','start_date':'2025-01-01','salary':'3000.00'});assert e.status_code==201,e.text
    r=c.post('/api/payroll',json={'employee_id':e.json()['id'],'period':'2026-09','allowances':'200','overtime':'100','deductions':'350'});assert r.status_code==201,r.text;p=r.json();assert Decimal(p['gross'])==3300;assert Decimal(p['net'])==2950
    assert c.post('/api/payroll',json={'employee_id':e.json()['id'],'period':'2026-09'}).status_code==409
    assert c.post('/api/payroll/'+p['id']+'/pay',json={'payment_date':str(date.today())}).status_code==409
    assert c.post('/api/payroll/'+p['id']+'/approve').status_code==200
    assert c.post('/api/payroll/'+p['id']+'/pay',json={'payment_date':str(date.today())}).status_code==200
    pdf=c.get('/api/payslips/'+p['id']+'/download');assert pdf.content.startswith(b'%PDF-')
    assert ctx['staff'].get('/api/payslips/'+p['id']+'/download').status_code==403

def test_upload_validation_hash_duplicates_and_private_access(ctx):
    c=ctx['staff'];assert c.post('/api/supplier-bills/upload',files={'file':('fake.pdf',b'<script>evil()</script>','application/pdf')}).status_code==422
    data=BytesIO();Image.new('RGB',(40,40),'white').save(data,'PNG');content=data.getvalue()
    a=c.post('/api/supplier-bills/upload',files={'file':('../../invoice.png',content,'image/png')});assert a.status_code==201,a.text
    b=c.post('/api/supplier-bills/upload',files={'file':('second.png',content,'image/png')});assert a.json()['id'] in b.json()['duplicate_ids']
    doc=a.json()['document_id'];assert c.get('/api/documents/'+doc+'/content').status_code==200
    assert ctx['other'].get('/api/documents/'+doc+'/content').status_code==404
    assert ctx['other'].get('/api/documents').status_code==403

def test_expected_invoice_evidence_and_resolution(ctx):
    b=verified(ctx);c=ctx['boss'];r=c.post('/api/expected-invoices',json={'supplier_id':b['supplier_id'],'expected_date':str(date.today()-timedelta(days=2)),'evidence':'Delivery note DN-123 confirmed'});assert r.status_code==201
    assert c.get('/api/expected-invoices').json()['items'][0]['display_status']=='potentially_missing'
    assert c.post('/api/expected-invoices/'+r.json()['id']+'/resolve',json={'status':'resolved','resolution':'Invoice arrived'}).status_code==422
    assert c.post('/api/expected-invoices/'+r.json()['id']+'/resolve',json={'status':'resolved','bill_id':b['id'],'resolution':'Invoice received and verified'}).status_code==200

def test_disabled_user_sessions_and_origin(ctx):
    c=ctx['boss'];users=c.get('/api/users').json()['items'];staff=next(u for u in users if u['role']=='STAFF')
    assert c.put('/api/users/'+staff['id']+'/access',json={'role':'STAFF','active':False}).status_code==200
    assert ctx[staff['name']].get('/api/auth/me').status_code==401
    assert c.post('/api/suppliers',json={'name':'Blocked'},headers={'Origin':'https://attacker.example'}).status_code==403

def test_report_csv_formula_safety(ctx):
    c=ctx['boss'];s=c.post('/api/suppliers',json={'name':'=HYPERLINK("bad")'}).json();b=invoice(ctx,s['id']);c.post('/api/supplier-bills/'+b['id']+'/verify',json={'version':1})
    r=c.get('/api/reports?export=true');assert r.status_code==200;assert "'=HYPERLINK" in r.text
