import csv
import io
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy import select, func, delete, or_, cast, String
from sqlalchemy.orm import Session
from .db import get_db
from .models import Bill, Supplier, Payment, Allocation, Audit, Employee, Payroll, Document, User, Role, Session as UserSession, ExpectedInvoice, BusinessSetting
from .schemas import UserIn, UserAccessIn, SettingIn
from .security import require, current_user, hash_password, audit, BOSS_PERMISSIONS, STAFF_PERMISSIONS
from .services import columns, page, bill_json, paid_query, OFFICIAL
from .storage import storage
from .config import settings

router=APIRouter(tags=['Operations'])

@router.get('/dashboard')
def dashboard(user=Depends(require('dashboard.read')),db:Session=Depends(get_db)):
    paid=paid_query();remaining=Bill.total-func.coalesce(paid.c.paid,0)
    financial=select(Bill).outerjoin(paid,Bill.id==paid.c.bill_id).where(Bill.status.in_(OFFICIAL),Bill.archived_at==None)
    outstanding=db.scalar(select(func.coalesce(func.sum(remaining),0)).select_from(Bill).outerjoin(paid,Bill.id==paid.c.bill_id).where(Bill.status.in_(OFFICIAL),Bill.archived_at==None))
    overdue=db.scalar(select(func.count()).select_from(financial.where(remaining>0,Bill.due_date<date.today()).subquery()))
    counts=dict(db.execute(select(Bill.status,func.count()).where(Bill.archived_at==None).group_by(Bill.status)).all())
    missing=db.scalar(select(func.count()).select_from(ExpectedInvoice).where(ExpectedInvoice.status=='expected',ExpectedInvoice.expected_date<date.today()))
    duplicate_count=db.scalar(select(func.count()).select_from(Bill).where(Bill.archived_at==None,cast(Bill.duplicate_ids,String)!='[]',Bill.duplicate_resolution=='',Bill.status!='rejected'))
    attention=list(db.scalars(select(Bill).where(Bill.archived_at==None,Bill.status.in_(['needs_review','processing_failed'])).order_by(Bill.created_at.desc()).limit(6)))
    due=list(db.scalars(financial.where(remaining>0).order_by(Bill.due_date).limit(5)))
    activity=[columns(a) for a in db.scalars(select(Audit).where(Audit.action.notin_(['login','logout','employee_sensitive_viewed','document_viewed'])).order_by(Audit.created_at.desc()).limit(8))]
    trend=[]
    for offset in range(5,-1,-1):
        idx=date.today().year*12+date.today().month-1-offset;start=date(idx//12,idx%12+1,1);nextidx=idx+1;end=date(nextidx//12,nextidx%12+1,1)
        value=db.scalar(select(func.coalesce(func.sum(Bill.total),0)).where(Bill.status.in_(OFFICIAL),Bill.invoice_date>=start,Bill.invoice_date<end))
        trend.append({'month':start.strftime('%b'),'total':value})
    return {'outstanding':outstanding,'overdue':overdue,'total_bills':sum(counts.values()),'needs_review':counts.get('needs_review',0),'failed':counts.get('processing_failed',0),'processing':counts.get('processing',0),'missing':missing,'duplicates':duplicate_count,'attention':[bill_json(db,b) for b in attention],'due':[bill_json(db,b) for b in due],'activity':activity,'trend':trend}

@router.get('/documents')
def documents(q:str='',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('documents.manage')),db:Session=Depends(get_db)):
    query=select(Document).where(Document.name.ilike(f'%{q[:100]}%'))
    if user.role!='BOSS':query=query.where(Document.owner_id==user.id,Document.category=='invoice')
    rows,total=page(db,query.order_by(Document.created_at.desc()),page_number,page_size)
    return {'items':[columns(d,('key','owner_id')) for d in rows],'total':total}

@router.get('/documents/{id}/content')
def document_content(id:str,download:bool=False,user=Depends(current_user),db:Session=Depends(get_db)):
    d=db.get(Document,id)
    if not d or (user.role!='BOSS' and (d.owner_id!=user.id or d.category not in ['invoice','wastage'])):raise HTTPException(404,'Document not found')
    audit(db,user,'document_downloaded' if download else 'document_viewed','document',id)
    extension={'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg'}[d.mime]
    return Response(storage.get(d.key),media_type=d.mime,headers={'Content-Disposition':f'{"attachment" if download else "inline"}; filename="document-{id[:8]}.{extension}"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})

@router.get('/audit')
def audit_list(q:str='',entity:str='',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('audit.read')),db:Session=Depends(get_db)):
    query=select(Audit).where(or_(Audit.action.ilike(f'%{q[:100]}%'),Audit.actor_name.ilike(f'%{q[:100]}%')))
    if entity:query=query.where(Audit.entity==entity)
    rows,total=page(db,query.order_by(Audit.created_at.desc()),page_number,page_size);return {'items':[columns(a) for a in rows],'total':total}

@router.get('/reports')
def reports(date_from:date|None=None,date_to:date|None=None,supplier_id:str='',export:bool=False,user=Depends(require('reports.read')),db:Session=Depends(get_db)):
    paid=paid_query();query=select(Supplier.name,func.count(Bill.id).label('bills'),func.sum(Bill.total).label('invoiced'),func.sum(func.coalesce(paid.c.paid,0)).label('paid'),func.sum(Bill.total-func.coalesce(paid.c.paid,0)).label('outstanding')).join(Bill,Bill.supplier_id==Supplier.id).outerjoin(paid,paid.c.bill_id==Bill.id).where(Bill.status.in_(OFFICIAL))
    if date_from:query=query.where(Bill.invoice_date>=date_from)
    if date_to:query=query.where(Bill.invoice_date<=date_to)
    if supplier_id:query=query.where(Supplier.id==supplier_id)
    rows=[dict(r) for r in db.execute(query.group_by(Supplier.id,Supplier.name).order_by(func.sum(Bill.total).desc()).limit(1000)).mappings()]
    if export:
        stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['Supplier','Bills','Invoiced MYR','Paid MYR','Outstanding MYR'])
        for row in rows:writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in row.values()])
        audit(db,user,'report_exported','report','supplier-spending')
        return Response('\ufeff'+stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="supplier-report.csv"'})
    payroll_query=select(Payroll.period,func.sum(Payroll.basic+Payroll.allowances+Payroll.overtime).label('gross'),func.sum(Payroll.deductions).label('deductions'),func.sum(Payroll.basic+Payroll.allowances+Payroll.overtime-Payroll.deductions).label('net')).where(Payroll.status.in_(['approved','paid']))
    if date_from:payroll_query=payroll_query.where(Payroll.period>=date_from.strftime('%Y-%m'))
    if date_to:payroll_query=payroll_query.where(Payroll.period<=date_to.strftime('%Y-%m'))
    payroll=[dict(r) for r in db.execute(payroll_query.group_by(Payroll.period).order_by(Payroll.period.desc()).limit(24)).mappings()]
    return {'suppliers':rows,'payroll':payroll,'basis':'Verified and approved invoices by invoice date; allocations recorded to date. Payroll includes approved and paid records. Up to 1,000 suppliers and 24 payroll periods.'}

@router.get('/users')
def users(user=Depends(require('users.manage')),db:Session=Depends(get_db)):
    return {'items':[columns(u,('password_hash',)) for u in db.scalars(select(User).order_by(User.name).limit(100))]}

@router.post('/users',status_code=201)
def create_user(data:UserIn,user=Depends(require('users.manage')),db:Session=Depends(get_db)):
    u=User(name=data.name,email=data.email.lower(),role=data.role,password_hash=hash_password(data.password));db.add(u);db.flush();audit(db,user,'user_created','user',u.id,{'role':u.role,'email':u.email});return columns(u,('password_hash',))

@router.put('/users/{id}/access')
def user_access(id:str,data:UserAccessIn,user=Depends(require('users.manage')),db:Session=Depends(get_db)):
    if id==user.id:raise HTTPException(422,'Ask another owner to change your own access')
    owners=list(db.scalars(select(User).where(User.role=='BOSS',User.active==True).order_by(User.id).with_for_update()))
    if any(u.id==id for u in owners) and len(owners)==1 and (data.role!='BOSS' or not data.active):
        raise HTTPException(409,'At least one active business owner is required')
    u=db.scalar(select(User).where(User.id==id).with_for_update())
    if not u:raise HTTPException(404,'User not found')
    before={'role':u.role,'active':u.active};u.role=data.role;u.active=data.active
    db.execute(delete(UserSession).where(UserSession.user_id==id));audit(db,user,'user_access_changed','user',id,{'before':before,'after':data.model_dump()});return columns(u,('password_hash',))

@router.get('/roles')
def roles(user=Depends(require('users.manage')),db:Session=Depends(get_db)):
    return [{'name':r.name,'permissions':r.permissions} for r in db.scalars(select(Role))]

@router.get('/settings')
def read_settings(user=Depends(require('settings.manage')),db:Session=Depends(get_db)):
    s=db.get(BusinessSetting,'company_name')
    gemini_ready=settings.extraction_provider=='gemini' and bool(settings.gemini_api_key) and (not settings.free_only or settings.gemini_free_tier_confirmed)
    return {'company_name':s.value if s else settings.company_name,'business_type':settings.business_type,'currency':'MYR','ocr_configured':gemini_ready if settings.extraction_provider=='gemini' else settings.ocr_provider=='local' or bool(settings.ocr_endpoint),'ai_configured':gemini_ready or (settings.extraction_provider=='ollama' and bool(settings.extraction_endpoint)),'extraction_mode':settings.extraction_provider,'free_only':settings.free_only,'environment':settings.environment}

@router.put('/settings')
def edit_settings(data:SettingIn,user=Depends(require('settings.manage')),db:Session=Depends(get_db)):
    db.merge(BusinessSetting(key='company_name',value=data.company_name));audit(db,user,'settings_updated','settings','company_name',data.model_dump());return data
