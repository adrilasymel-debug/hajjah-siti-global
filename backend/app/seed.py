"""Explicit, repeatable development seed. Never called during application startup."""
import hashlib
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from sqlalchemy import select
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from .config import settings
from .db import SessionLocal
from .models import Role,User,Supplier,Bill,LineItem,Payment,Allocation,Employee,Payroll,ExpectedInvoice,Document,Audit,now
from .security import hash_password, BOSS_PERMISSIONS,STAFF_PERMISSIONS,audit
from .storage import storage

def invoice_pdf(supplier,number,total,invoice_date):
    out=BytesIO();c=canvas.Canvas(out,pagesize=(595,842));c.setTitle('DEMO invoice '+number)
    c.setFillColor(HexColor('#193a49'));c.setFont('Helvetica-Bold',21);c.drawString(48,777,supplier[:42]);c.setFont('Helvetica',10);c.drawString(48,753,'DEMONSTRATION DOCUMENT - NOT A REAL INVOICE')
    c.setFont('Helvetica-Bold',24);c.drawString(48,681,'INVOICE');c.setFont('Helvetica',11);c.drawString(48,650,number);c.drawRightString(547,650,str(invoice_date))
    c.setFont('Helvetica-Bold',11);c.drawString(48,593,'BILL TO');c.setFont('Helvetica',11);c.drawString(48,571,'Family Operations (Demonstration)');c.drawString(48,551,'Kuala Lumpur, Malaysia')
    c.setFillColor(HexColor('#eff4f6'));c.rect(48,464,499,35,fill=1,stroke=0);c.setFillColor(HexColor('#193a49'));c.setFont('Helvetica-Bold',10);c.drawString(60,477,'DESCRIPTION');c.drawRightString(535,477,'AMOUNT (MYR)')
    c.setFont('Helvetica',11);c.drawString(60,438,'Business supplies and materials');c.drawRightString(535,438,f'{total:,.2f}');c.setStrokeColor(HexColor('#d8e3e9'));c.line(48,419,547,419)
    c.drawString(355,366,'Subtotal');c.drawRightString(535,366,f'{total:,.2f}');c.drawString(355,340,'Tax');c.drawRightString(535,340,'0.00');c.setFont('Helvetica-Bold',15);c.drawString(355,301,'TOTAL');c.drawRightString(535,301,f'{total:,.2f}')
    c.setFont('Helvetica',10);c.drawString(48,190,'Payment terms: 30 days');c.drawString(48,164,'Please quote the invoice number with your payment.');c.setFillColor(HexColor('#8398a4'));c.drawString(48,65,'Sample data for development and training only.');c.showPage();c.save();return out.getvalue()

def seed():
    if settings.environment=='production':raise RuntimeError('Demo seed is blocked in production')
    if len(settings.demo_password)<12:raise RuntimeError('Set DEMO_PASSWORD to a password of at least 12 characters')
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email=='owner@demo.local')):print('Demo data already exists. No changes made.');return
        db.merge(Role(name='BOSS',permissions=BOSS_PERMISSIONS));db.merge(Role(name='STAFF',permissions=STAFF_PERMISSIONS));db.flush()
        boss=User(name='Aiman Rahman',email='owner@demo.local',role='BOSS',password_hash=hash_password(settings.demo_password))
        staff=User(name='Nur Aisyah',email='staff@demo.local',role='STAFF',password_hash=hash_password(settings.demo_password));db.add_all([boss,staff]);db.flush()
        suppliers=[]
        for name,contact,terms in [('Maju Jaya Packaging','Daniel Tan',30),('Sinar Food Industries','Farah Ismail',30),('Kencana Trading','Wong Mei Ling',45),('Evergreen Office Supply','Jason Lee',14),('Bumi Fresh Distribution','Hafiz Abdullah',30),('Metro Logistics','Sarah Lim',30)]:
            s=Supplier(name=name,contact=contact,payment_terms=terms,email=name.lower().split()[0]+'@example.com',phone='+60 3 5550 1200',address='Kuala Lumpur, Malaysia',registration='DEMO-2026-'+str(len(suppliers)+101));db.add(s);db.flush();suppliers.append(s);audit(db,boss,'supplier_created','supplier',s.id,{'name':s.name,'demo':True})
        amounts=[Decimal(x) for x in ['4850','12640','3280','890','7620','2150','5400','18300','4250','1260','9600','3450','6700','22100','3580','1575','14200','8900']]
        for i,amount in enumerate(amounts):
            supplier=suppliers[i%6];invoice_date=date.today()-timedelta(days=i*9+2);number=f'{["MJP","SFI","KT","EOS","BFD","ML"][i%6]}-2026-{1048+i}'
            status='needs_review' if i<4 else 'verified' if i%3 else 'approved';due=invoice_date+timedelta(days=supplier.payment_terms)
            data=invoice_pdf(supplier.name,number,amount,invoice_date);key=storage.put(data,'application/pdf');doc=Document(name=number+'.pdf',key=key,mime='application/pdf',size=len(data),sha256=hashlib.sha256(data).hexdigest(),owner_id=staff.id);db.add(doc);db.flush()
            bill=Bill(supplier_id=supplier.id,document_id=doc.id,submitted_by=staff.id,number=number,invoice_date=invoice_date,due_date=due,subtotal=amount,tax=0,total=amount,status=status,created_at=now()-timedelta(hours=i*5),review={'message':'Demonstration record. Compare with the sample original before verifying.'} if i<4 else {})
            if status in ['verified','approved']:bill.verified_at=now()-timedelta(days=1);bill.verified_by=staff.id
            bill.items=[LineItem(description='Business supplies and materials',quantity=1,unit_price=amount,tax=0,total=amount)];db.add(bill);db.flush();audit(db,staff,'invoice_uploaded' if i<4 else 'invoice_verified','bill',bill.id,{'number':number,'demo':True})
            if i>=4 and i%4 in [0,1]:
                payment=Payment(supplier_id=supplier.id,payment_date=date.today()-timedelta(days=1),reference=f'DEMO-TRF-{920+i}',method='bank_transfer',notes='Demonstration payment',created_by=boss.id,idempotency_key=f'demo-payment-{i}')
                payment.allocations=[Allocation(bill_id=bill.id,amount=amount if i%4==0 else amount/2)];db.add(payment);db.flush();audit(db,boss,'payment_recorded','bill',bill.id,{'reference':payment.reference,'amount':str(payment.allocations[0].amount)})
        for i in range(3):db.add(ExpectedInvoice(supplier_id=suppliers[i].id,expected_date=date.today()-timedelta(days=3+i*2),evidence=f'Demo delivery note DN-{240+i}; supplier confirmed invoice would follow.'))
        for i,(name,position,department,salary) in enumerate([('Siti Nurhaliza','Operations manager','Operations',5500),('Ahmad Firdaus','Warehouse supervisor','Warehouse',3800),('Lim Jia Wei','Accounts executive','Finance',4200),('Priya Devi','Purchasing assistant','Purchasing',3200)]):
            e=Employee(employee_code=f'EMP-{i+1:03}',name=name,position=position,department=department,start_date=date(2023+i%2,3,1),salary=salary,email=f'employee{i+1}@example.com',bank_name='Demo bank',bank_account='DEMO-'+str(i+1));db.add(e);db.flush()
            p=Payroll(period=date.today().strftime('%Y-%m'),employee_id=e.id,employee_name=e.name,employee_code=e.employee_code,basic=salary,allowances=200,overtime=0,deductions=0,status='draft' if i==3 else 'approved');db.add(p);db.flush();audit(db,boss,'payroll_generated','payroll',p.id,{'employee':name,'demo':True})
        db.commit();print('Demo records created. Accounts: owner@demo.local and staff@demo.local. Password: the DEMO_PASSWORD you supplied.')

if __name__=='__main__':seed()
