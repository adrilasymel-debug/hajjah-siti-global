from io import BytesIO
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from .db import get_db
from .models import Employee, Payroll, BusinessSetting
from .schemas import EmployeeIn, PayrollIn, PayrollPayIn
from .security import require, audit
from .services import columns, page, money
from .config import settings

router=APIRouter(tags=['People and payroll'])

@router.get('/employees')
def employees(q:str='',department:str='',active:bool|None=None,page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('employees.manage')),db:Session=Depends(get_db)):
    query=select(Employee).where(Employee.name.ilike(f'%{q[:100]}%'))
    if department:query=query.where(Employee.department==department)
    if active is not None:query=query.where(Employee.active==active)
    rows,total=page(db,query.order_by(Employee.name),page_number,page_size)
    return {'items':[columns(e,('bank_account',)) for e in rows],'total':total}

@router.get('/employees/{id}')
def employee(id:str,user=Depends(require('employees.manage')),db:Session=Depends(get_db)):
    e=db.get(Employee,id)
    if not e:raise HTTPException(404,'Employee not found')
    audit(db,user,'employee_sensitive_viewed','employee',id)
    return columns(e)

@router.post('/employees',status_code=201)
def create_employee(data:EmployeeIn,user=Depends(require('employees.manage')),db:Session=Depends(get_db)):
    e=Employee(**data.model_dump());db.add(e);db.flush();audit(db,user,'employee_created','employee',e.id,{'name':e.name});return columns(e,('bank_account',))

@router.put('/employees/{id}')
def edit_employee(id:str,data:EmployeeIn,user=Depends(require('employees.manage')),db:Session=Depends(get_db)):
    e=db.get(Employee,id)
    if not e:raise HTTPException(404,'Employee not found')
    changed=[k for k,v in data.model_dump().items() if getattr(e,k)!=v]
    salary_before=str(e.salary)
    for k,v in data.model_dump().items():setattr(e,k,v)
    audit(db,user,'employee_updated','employee',id,{'changed_fields':changed,'salary_before':salary_before,'salary_after':str(e.salary)})
    return columns(e,('bank_account',))

def payroll_json(p):
    gross=money(p.basic+p.allowances+p.overtime)
    return {**columns(p),'gross':gross,'net':money(gross-p.deductions)}

@router.get('/payroll')
@router.get('/payslips')
def payroll(period:str='',q:str='',page_number:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(require('payroll.manage')),db:Session=Depends(get_db)):
    query=select(Payroll).where(Payroll.employee_name.ilike(f'%{q[:100]}%'))
    if period:query=query.where(Payroll.period==period)
    rows,total=page(db,query.order_by(Payroll.period.desc(),Payroll.employee_name),page_number,page_size)
    return {'items':[payroll_json(p) for p in rows],'total':total}

@router.post('/payroll',status_code=201)
def generate_payroll(data:PayrollIn,user=Depends(require('payroll.manage')),db:Session=Depends(get_db)):
    e=db.get(Employee,data.employee_id)
    if not e or not e.active:raise HTTPException(422,'Select an active employee')
    if db.scalar(select(Payroll.id).where(Payroll.employee_id==e.id,Payroll.period==data.period)):raise HTTPException(409,'Payroll already exists for this employee and period')
    if data.deductions>e.salary+data.allowances+data.overtime:raise HTTPException(422,'Deductions cannot exceed gross pay')
    p=Payroll(**data.model_dump(),employee_name=e.name,employee_code=e.employee_code,basic=e.salary)
    db.add(p);db.flush();audit(db,user,'payroll_generated','payroll',p.id,{'period':p.period,'employee':e.name});return payroll_json(p)

@router.post('/payroll/{id}/approve')
def approve_payroll(id:str,user=Depends(require('payroll.manage')),db:Session=Depends(get_db)):
    p=db.scalar(select(Payroll).where(Payroll.id==id).with_for_update())
    if not p:raise HTTPException(404,'Payroll not found')
    if p.status!='draft':raise HTTPException(409,'Only draft payroll can be approved')
    p.status='approved';audit(db,user,'payroll_approved','payroll',id);return payroll_json(p)

@router.post('/payroll/{id}/pay')
def pay_payroll(id:str,data:PayrollPayIn,user=Depends(require('payroll.manage')),db:Session=Depends(get_db)):
    p=db.scalar(select(Payroll).where(Payroll.id==id).with_for_update())
    if not p or p.status!='approved':raise HTTPException(409,'Approve this payroll first')
    p.status='paid';p.payment_date=data.payment_date;audit(db,user,'payroll_paid','payroll',id,{'payment_date':str(data.payment_date)});return payroll_json(p)

def payslip_pdf(p,company):
    output=BytesIO();c=canvas.Canvas(output,pagesize=(595,842));c.setTitle(f'Payslip {p.period} {p.employee_code}')
    c.setFillColor(HexColor('#102c3a'));c.rect(0,702,595,140,fill=1,stroke=0)
    c.setFillColor(HexColor('#ffffff'));c.setFont('Helvetica-Bold',22);c.drawString(48,784,company[:42]);c.setFont('Helvetica',12);c.drawString(48,755,'PAYSLIP  /  '+p.period)
    c.setFillColor(HexColor('#102c3a'));c.setFont('Helvetica-Bold',16);c.drawString(48,653,p.employee_name[:50]);c.setFont('Helvetica',11);c.drawString(48,630,f'{p.employee_code}  |  Status: {p.status.title()}')
    y=565
    for label,value in [('Basic salary',p.basic),('Allowances',p.allowances),('Overtime',p.overtime),('Gross pay',p.basic+p.allowances+p.overtime),('Deductions',p.deductions),('Net pay',p.basic+p.allowances+p.overtime-p.deductions)]:
        c.setFont('Helvetica-Bold' if label in ['Gross pay','Net pay'] else 'Helvetica',12);c.drawString(48,y,label);c.drawRightString(547,y,f'MYR {value:,.2f}');c.setStrokeColor(HexColor('#e0e6eb'));c.line(48,y-15,547,y-15);y-=49
    c.setFont('Helvetica',10);c.drawString(48,190,'Payment date: '+(str(p.payment_date) if p.payment_date else 'Not yet recorded'))
    c.drawString(48,164,'Deductions reflect the amounts entered and approved by your employer.')
    if p.status=='draft':c.drawString(48,140,'DRAFT - awaiting approval')
    c.setFont('Helvetica',9);c.drawString(48,65,'Confidential | Generated by Family Operations');c.showPage();c.save();return output.getvalue()

@router.get('/payslips/{id}/download')
def download_payslip(id:str,user=Depends(require('payroll.manage')),db:Session=Depends(get_db)):
    p=db.get(Payroll,id)
    if not p:raise HTTPException(404,'Payslip not found')
    company=db.get(BusinessSetting,'company_name');audit(db,user,'payslip_downloaded','payroll',id)
    return Response(payslip_pdf(p,company.value if company else settings.company_name),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="payslip-{p.period}-{p.id[:8]}.pdf"','Cache-Control':'no-store'})
