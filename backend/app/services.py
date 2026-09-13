from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, func, or_, and_
from .models import Bill, Allocation, Document, Supplier, LineItem, Payment

OFFICIAL = ['verified', 'approved']
def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def paid_query():
    return select(Allocation.bill_id, func.sum(Allocation.amount).label('paid')).join(Payment).where(Payment.voided_at==None).group_by(Allocation.bill_id).subquery()

def balance(db, bill):
    paid = db.scalar(select(func.coalesce(func.sum(Allocation.amount), 0)).join(Payment).where(Allocation.bill_id == bill.id,Payment.voided_at==None))
    return money(bill.total - paid), money(paid)

def payment_status(bill, outstanding, paid):
    if bill.status not in OFFICIAL: return 'not_payable'
    if outstanding <= 0: return 'paid'
    if bill.due_date and bill.due_date < date.today(): return 'overdue'
    return 'partially_paid' if paid else 'unpaid'

def bill_json(db, bill, detail=False, known_paid=None):
    outstanding, paid = balance(db, bill) if known_paid is None else (money(bill.total-known_paid), money(known_paid))
    result = {k: getattr(bill, k) for k in ['id','number','supplier_id','document_id','invoice_date','due_date','currency','subtotal','tax','total','status','notes','created_at','version','verified_at','verified_by','duplicate_ids','duplicate_resolution','review']}
    result.update(supplier_name=bill.supplier.name if bill.supplier else 'Supplier needs matching', paid=paid,
                  outstanding=outstanding if bill.status in OFFICIAL else Decimal(0), payment_status=payment_status(bill, outstanding, paid))
    if detail:
        result['items'] = [{k:getattr(i,k) for k in ['id','description','unit','quantity','unit_price','tax','total']} for i in bill.items]
    return result

def detect_duplicates(db, bill):
    indicators = []
    if bill.number and bill.supplier_id:
        indicators.append(and_(Bill.supplier_id == bill.supplier_id, func.lower(Bill.number) == bill.number.strip().lower()))
    if bill.supplier_id and bill.invoice_date and bill.total > 0:
        indicators.append(and_(Bill.supplier_id == bill.supplier_id, Bill.invoice_date == bill.invoice_date, Bill.total == bill.total))
    if bill.document_id:
        doc = db.get(Document, bill.document_id)
        indicators.append(Bill.document_id.in_(select(Document.id).where(Document.sha256 == doc.sha256)))
    ids = list(db.scalars(select(Bill.id).where(Bill.id != bill.id, or_(*indicators)))) if indicators else []
    bill.duplicate_ids = ids
    return ids

def validate_bill(db, bill):
    if not bill.supplier_id or not db.get(Supplier, bill.supplier_id): raise HTTPException(422, 'Select a supplier')
    if not bill.number or not bill.invoice_date or not bill.due_date: raise HTTPException(422, 'Invoice number and both dates are required')
    if bill.invoice_date > date.today(): raise HTTPException(422, 'Invoice date cannot be in the future')
    if bill.due_date < bill.invoice_date: raise HTTPException(422, 'Due date cannot precede invoice date')
    if bill.total <= 0 or money(bill.subtotal + bill.tax) != money(bill.total): raise HTTPException(422, 'Subtotal plus tax must equal a positive invoice total')
    if bill.items:
        for item in bill.items:
            if money(item.quantity * item.unit_price + item.tax) != money(item.total):
                raise HTTPException(422, 'A line total does not match quantity × unit price plus tax')
        if money(sum(i.total for i in bill.items)) != money(bill.total): raise HTTPException(422, 'Line items must add up to the invoice total')
        if money(sum(i.tax for i in bill.items)) != money(bill.tax): raise HTTPException(422, 'Line taxes must add up to invoice tax')

def apply_bill(db, bill, data):
    values = data.model_dump(exclude={'version','supplier_name'})
    if values['supplier_id'] and not db.get(Supplier, values['supplier_id']): raise HTTPException(422, 'Supplier does not exist')
    bill.items = [LineItem(**item) for item in values.pop('items')]
    for key,value in values.items(): setattr(bill,key,value)

def page(db, query, page_number, page_size):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return list(db.scalars(query.offset((page_number-1)*page_size).limit(page_size))), total

def columns(record, exclude=()):
    return {c.name: getattr(record,c.name) for c in record.__table__.columns if c.name not in exclude}
