import hashlib
from datetime import date
from pathlib import PurePath
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.orm import Session, selectinload
from .db import get_db
from .models import Supplier, Bill, Document, Job, Payment, Allocation, ExpectedInvoice, Audit, now
from .schemas import SupplierIn, BillCreate, BillEdit, VerifyIn, ReasonIn, PaymentIn, ExpectedIn, ResolveIn
from .security import current_user, require, can_read_bill, audit
from .services import columns, page, bill_json, apply_bill, detect_duplicates, validate_bill, balance, OFFICIAL, paid_query
from .storage import storage, validate_file
from .config import settings

router=APIRouter(tags=['Purchasing'])

def resolve_invoice_supplier(db,user,data):
    """Create/match a name in the invoice transaction, after invoice access checks."""
    if not data.supplier_name:return
    name=data.supplier_name.strip()
    # Serialize simultaneous inline requests for the same name in PostgreSQL.
    if db.bind.dialect.name=='postgresql':
        lock=int.from_bytes(hashlib.sha256(name.lower().encode()).digest()[:8],'big',signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lock})
    matches=list(db.scalars(select(Supplier).where(func.lower(func.trim(Supplier.name))==name.lower()).limit(2)))
    if len(matches)>1:raise HTTPException(422,'Several suppliers have this name. Select the existing supplier from the suggestions.')
    if matches:
        supplier=matches[0]
        if not supplier.active:raise HTTPException(422,'This supplier is inactive. Ask the owner to reactivate it before using this name.')
    else:
        supplier=Supplier(name=name);db.add(supplier);db.flush()
        audit(db,user,'supplier_created','supplier',supplier.id,{'name':name,'source':'invoice_review'})
    data.supplier_id=supplier.id

@router.get('/suppliers/lookup')
def supplier_lookup(q:str='',user=Depends(current_user),db:Session=Depends(get_db)):
    return [dict(id=s.id,name=s.name) for s in db.scalars(select(Supplier).where(Supplier.active==True,Supplier.name.ilike(f'%{q[:100]}%')).order_by(Supplier.name).limit(100))]

@router.get('/suppliers')
def suppliers(q:str='',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('suppliers.manage')),db:Session=Depends(get_db)):
    rows,total=page(db,select(Supplier).where(Supplier.name.ilike(f'%{q[:100]}%')).order_by(Supplier.name),page_number,page_size)
    result=[]; paid=paid_query()
    for s in rows:
        outstanding=db.scalar(select(func.coalesce(func.sum(Bill.total-func.coalesce(paid.c.paid,0)),0)).outerjoin(paid,Bill.id==paid.c.bill_id).where(Bill.supplier_id==s.id,Bill.status.in_(OFFICIAL)))
        result.append({**columns(s),'outstanding':outstanding})
    return {'items':result,'total':total}

@router.post('/suppliers',status_code=201)
def create_supplier(data:SupplierIn,user=Depends(require('suppliers.manage')),db:Session=Depends(get_db)):
    s=Supplier(**data.model_dump());db.add(s);db.flush();audit(db,user,'supplier_created','supplier',s.id,{'name':s.name});return columns(s)

@router.put('/suppliers/{id}')
def edit_supplier(id:str,data:SupplierIn,user=Depends(require('suppliers.manage')),db:Session=Depends(get_db)):
    s=db.get(Supplier,id)
    if not s:raise HTTPException(404,'Supplier not found')
    before=columns(s,('created_at','updated_at'))
    for k,v in data.model_dump().items():setattr(s,k,v)
    audit(db,user,'supplier_updated','supplier',id,{'before':before,'after':data.model_dump(mode='json')});return columns(s)

@router.get('/suppliers/{id}')
def supplier_detail(id:str,user=Depends(require('suppliers.manage')),db:Session=Depends(get_db)):
    s=db.get(Supplier,id)
    if not s:raise HTTPException(404,'Supplier not found')
    bills=list(db.scalars(select(Bill).where(Bill.supplier_id==id).order_by(Bill.created_at.desc()).limit(20)))
    paid=paid_query()
    outstanding=db.scalar(select(func.coalesce(func.sum(Bill.total-func.coalesce(paid.c.paid,0)),0)).outerjoin(paid,Bill.id==paid.c.bill_id).where(Bill.supplier_id==id,Bill.status.in_(OFFICIAL)))
    payments=list(db.scalars(select(Payment).where(Payment.supplier_id==id).order_by(Payment.created_at.desc()).limit(20)))
    return {**columns(s),'outstanding':outstanding,'bills':[bill_json(db,b) for b in bills],'payments':[payment_json(p) for p in payments]}

@router.get('/supplier-bills')
def bills(q:str='',supplier_id:str='',status:str='',payment_status:str='',date_from:date|None=None,date_to:date|None=None,amount_min:float|None=None,amount_max:float|None=None,sort:str='newest',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(current_user),db:Session=Depends(get_db)):
    paid=paid_query();paid_amount=func.coalesce(paid.c.paid,0)
    query=select(Bill).outerjoin(Supplier).outerjoin(paid,Bill.id==paid.c.bill_id).options(selectinload(Bill.supplier))
    if user.role!='BOSS':query=query.where(Bill.submitted_by==user.id)
    if q:query=query.where(or_(Bill.number.ilike(f'%{q[:100]}%'),Supplier.name.ilike(f'%{q[:100]}%')))
    if supplier_id:query=query.where(Bill.supplier_id==supplier_id)
    if status:query=query.where(Bill.status==status)
    if date_from:query=query.where(Bill.invoice_date>=date_from)
    if date_to:query=query.where(Bill.invoice_date<=date_to)
    if amount_min is not None:query=query.where(Bill.total>=amount_min)
    if amount_max is not None:query=query.where(Bill.total<=amount_max)
    if payment_status:
        query=query.where(Bill.status.in_(OFFICIAL))
        if payment_status=='paid':query=query.where(paid_amount>=Bill.total)
        elif payment_status=='overdue':query=query.where(Bill.total>paid_amount,Bill.due_date<date.today())
        elif payment_status=='unpaid':query=query.where(paid_amount==0,Bill.total>0,or_(Bill.due_date>=date.today(),Bill.due_date==None))
        elif payment_status=='partially_paid':query=query.where(paid_amount>0,Bill.total>paid_amount,or_(Bill.due_date>=date.today(),Bill.due_date==None))
    query=query.order_by({'newest':Bill.created_at.desc(),'oldest':Bill.created_at.asc(),'amount':Bill.total.desc(),'due':Bill.due_date.asc()}.get(sort,Bill.created_at.desc()),Bill.id)
    rows,total=page(db,query,page_number,page_size)
    paid_map=dict(db.execute(select(Allocation.bill_id,func.sum(Allocation.amount)).join(Payment).where(Payment.voided_at==None,Allocation.bill_id.in_([b.id for b in rows])).group_by(Allocation.bill_id)).all())
    result=[bill_json(db,b,known_paid=paid_map.get(b.id,0)) for b in rows]
    if user.role!='BOSS':
        for item in result:item['duplicate_ids']=['possible duplicate'] if item['duplicate_ids'] else []
    return {'items':result,'total':total}

@router.post('/supplier-bills',status_code=201)
def create_bill(data:BillCreate,user=Depends(require('bills.create')),db:Session=Depends(get_db)):
    resolve_invoice_supplier(db,user,data)
    bill=Bill(submitted_by=user.id);apply_bill(db,bill,data);db.add(bill);db.flush();detect_duplicates(db,bill)
    audit(db,user,'invoice_created','bill',bill.id,{'number':bill.number});return bill_json(db,bill,True)

@router.post('/supplier-bills/upload',status_code=201)
async def upload(file:UploadFile=File(...),user=Depends(require('bills.create')),db:Session=Depends(get_db)):
    data=await file.read(settings.upload_limit_mb*1024*1024+1);mime=validate_file(data)
    key=storage.put(data,mime)
    try:
        name=(file.filename or 'invoice').replace('\\','/').split('/')[-1][:250]
        doc=Document(name=name,key=key,mime=mime,size=len(data),sha256=hashlib.sha256(data).hexdigest(),owner_id=user.id)
        db.add(doc);db.flush()
        bill=Bill(document_id=doc.id,submitted_by=user.id,status='processing');db.add(bill);db.flush()
        db.add(Job(bill_id=bill.id));detect_duplicates(db,bill)
        audit(db,user,'invoice_uploaded','bill',bill.id,{'filename':doc.name,'document_hash':doc.sha256})
        db.commit()
    except Exception:
        db.rollback();storage.delete(key);raise
    return bill_json(db,bill,True)

@router.get('/supplier-bills/{id}')
def bill_detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.get(Bill,id));data=bill_json(db,bill,True)
    data['history']=[columns(a) for a in db.scalars(select(Audit).where(Audit.entity=='bill',Audit.entity_id==id).order_by(Audit.created_at.desc()).limit(30))]
    data['payments']=[{'amount':a.amount,'date':p.payment_date,'reference':p.reference,'method':p.method,'voided':bool(p.voided_at)} for a,p in db.execute(select(Allocation,Payment).join(Payment).where(Allocation.bill_id==id)).all()]
    if bill.document_id:data['document']=columns(db.get(Document,bill.document_id),('key','owner_id'))
    # Never leak another staff member's invoice IDs through duplicate metadata.
    if user.role!='BOSS':data['duplicate_ids']=['possible duplicate'] if bill.duplicate_ids else []
    return data

@router.put('/supplier-bills/{id}')
def edit_bill(id:str,data:BillEdit,user=Depends(current_user),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.scalar(select(Bill).where(Bill.id==id).with_for_update()))
    if data.version!=bill.version:raise HTTPException(409,'This invoice changed. Reload before saving.')
    if bill.status=='processing':raise HTTPException(409,'Wait for processing to finish before editing')
    if bill.status in OFFICIAL and user.role!='BOSS':raise HTTPException(403,'Only the owner can correct verified records')
    if balance(db,bill)[1]>0:raise HTTPException(409,'Paid invoices are locked. Record a correcting document instead.')
    before={k:str(getattr(bill,k)) for k in ['supplier_id','number','invoice_date','due_date','subtotal','tax','total','status']}
    before['items']=[{k:str(getattr(i,k)) for k in ['description','quantity','unit_price','tax','total']} for i in bill.items]
    resolve_invoice_supplier(db,user,data)
    apply_bill(db,bill,data);bill.status='needs_review';bill.verified_at=None;bill.verified_by=None;bill.version+=1;bill.duplicate_resolution=''
    db.flush();detect_duplicates(db,bill)
    audit(db,user,'invoice_edited','bill',id,{'before':before,'after':data.model_dump(mode='json')});return bill_json(db,bill,True)

@router.post('/supplier-bills/{id}/verify')
def verify(id:str,data:VerifyIn,user=Depends(current_user),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.scalar(select(Bill).where(Bill.id==id).with_for_update()))
    if bill.version!=data.version:raise HTTPException(409,'This invoice changed. Reload before verifying.')
    if bill.status not in ['needs_review','processing_failed']:raise HTTPException(409,'Only reviewed invoices can be verified')
    validate_bill(db,bill);detect_duplicates(db,bill)
    if bill.duplicate_ids and (user.role!='BOSS' or len(data.duplicate_resolution)<5):raise HTTPException(409,'An owner must review and explain this possible duplicate before verification')
    bill.status='verified';bill.verified_by=user.id;bill.verified_at=now();bill.version+=1;bill.duplicate_resolution=data.duplicate_resolution
    audit(db,user,'invoice_verified','bill',id,{'duplicate_resolution':data.duplicate_resolution,'total':str(bill.total),'number':bill.number});return bill_json(db,bill,True)

@router.post('/supplier-bills/{id}/approve')
def approve(id:str,user=Depends(require('bills.manage')),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.scalar(select(Bill).where(Bill.id==id).with_for_update()))
    if bill.status!='verified':raise HTTPException(409,'Verify the invoice first')
    bill.status='approved';bill.version+=1;audit(db,user,'invoice_approved','bill',id);return bill_json(db,bill)

@router.post('/supplier-bills/{id}/reject')
def reject(id:str,data:ReasonIn,user=Depends(require('bills.manage')),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.scalar(select(Bill).where(Bill.id==id).with_for_update()))
    if balance(db,bill)[1]>0 or bill.status=='processing':raise HTTPException(409,'Paid or processing invoices cannot be rejected')
    bill.status='rejected';bill.version+=1;audit(db,user,'invoice_rejected','bill',id,{'reason':data.reason});return bill_json(db,bill)

@router.post('/supplier-bills/{id}/retry')
def retry(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    bill=can_read_bill(db,user,db.scalar(select(Bill).where(Bill.id==id).with_for_update()))
    if bill.status!='processing_failed' or not bill.document_id:raise HTTPException(409,'Only failed document processing can be retried')
    bill.status='processing';bill.version+=1;db.add(Job(bill_id=id));audit(db,user,'processing_retried','bill',id);return {'message':'Processing queued'}

def payment_json(p):return {**columns(p,('idempotency_key',)),'amount':sum(a.amount for a in p.allocations),'allocations':[columns(a) for a in p.allocations]}

@router.get('/payments')
def payments(q:str='',supplier_id:str='',date_from:date|None=None,date_to:date|None=None,method:str='',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('payments.manage')),db:Session=Depends(get_db)):
    query=select(Payment).where(Payment.reference.ilike(f'%{q[:100]}%'))
    if supplier_id:query=query.where(Payment.supplier_id==supplier_id)
    if date_from:query=query.where(Payment.payment_date>=date_from)
    if date_to:query=query.where(Payment.payment_date<=date_to)
    if method:query=query.where(Payment.method==method)
    rows,total=page(db,query.order_by(Payment.payment_date.desc()),page_number,page_size)
    return {'items':[{**payment_json(p),'supplier_name':db.get(Supplier,p.supplier_id).name} for p in rows],'total':total}

@router.post('/payments',status_code=201)
def create_payment(data:PaymentIn,user=Depends(require('payments.manage')),db:Session=Depends(get_db)):
    existing=db.scalar(select(Payment).where(Payment.idempotency_key==data.idempotency_key))
    if existing:return payment_json(existing)
    # Lock bills in a stable order; competing allocations cannot overpay a bill in PostgreSQL.
    locked={b.id:b for b in db.scalars(select(Bill).where(Bill.id.in_([a.bill_id for a in data.allocations])).order_by(Bill.id).with_for_update())}
    for a in data.allocations:
        b=locked.get(a.bill_id)
        if not b or b.supplier_id!=data.supplier_id or b.status not in OFFICIAL:raise HTTPException(422,'Select verified invoices from the same supplier')
        if a.amount>balance(db,b)[0]:raise HTTPException(409,'Payment exceeds the remaining invoice balance')
    payment=Payment(**data.model_dump(exclude={'allocations'}),created_by=user.id)
    payment.allocations=[Allocation(**a.model_dump()) for a in data.allocations];db.add(payment);db.flush()
    audit(db,user,'payment_created','payment',payment.id,{'reference':data.reference,'allocations':[a.model_dump(mode='json') for a in data.allocations]})
    for a in data.allocations:audit(db,user,'payment_recorded','bill',a.bill_id,{'reference':data.reference,'amount':str(a.amount)})
    return payment_json(payment)

@router.post('/payments/{id}/void')
def void_payment(id:str,data:ReasonIn,user=Depends(require('payments.manage')),db:Session=Depends(get_db)):
    payment=db.scalar(select(Payment).where(Payment.id==id).with_for_update())
    if not payment:raise HTTPException(404,'Payment not found')
    if payment.voided_at:raise HTTPException(409,'This payment is already voided')
    list(db.scalars(select(Bill).where(Bill.id.in_([a.bill_id for a in payment.allocations])).order_by(Bill.id).with_for_update()))
    payment.voided_at=now();payment.void_reason=data.reason
    audit(db,user,'payment_voided','payment',id,{'reference':payment.reference,'reason':data.reason})
    for a in payment.allocations:audit(db,user,'payment_voided','bill',a.bill_id,{'reference':payment.reference,'amount':str(a.amount),'reason':data.reason})
    return payment_json(payment)

@router.get('/expected-invoices')
def expected(page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('expected.manage')),db:Session=Depends(get_db)):
    rows,total=page(db,select(ExpectedInvoice).order_by(ExpectedInvoice.expected_date),page_number,page_size)
    return {'items':[{**columns(e),'supplier_name':db.get(Supplier,e.supplier_id).name,'display_status':'potentially_missing' if e.status=='expected' and e.expected_date<date.today() else e.status} for e in rows],'total':total}

@router.post('/expected-invoices',status_code=201)
def create_expected(data:ExpectedIn,user=Depends(require('expected.manage')),db:Session=Depends(get_db)):
    if not db.get(Supplier,data.supplier_id):raise HTTPException(422,'Supplier not found')
    e=ExpectedInvoice(**data.model_dump());db.add(e);db.flush();audit(db,user,'invoice_expected','expected',e.id,data.model_dump(mode='json'));return columns(e)

@router.post('/expected-invoices/{id}/resolve')
def resolve_expected(id:str,data:ResolveIn,user=Depends(require('expected.manage')),db:Session=Depends(get_db)):
    e=db.scalar(select(ExpectedInvoice).where(ExpectedInvoice.id==id).with_for_update())
    if not e:raise HTTPException(404,'Expected invoice not found')
    if e.status!='expected':raise HTTPException(409,'This expectation is already closed')
    if data.status=='resolved':
        b=db.get(Bill,data.bill_id) if data.bill_id else None
        if not b or b.supplier_id!=e.supplier_id or b.status not in OFFICIAL:raise HTTPException(422,'Link a verified invoice from this supplier')
    for k,v in data.model_dump().items():setattr(e,k,v)
    audit(db,user,'expected_invoice_'+data.status,'expected',id,data.model_dump(mode='json'));return columns(e)
