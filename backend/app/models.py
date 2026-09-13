from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import String, Text, ForeignKey, Numeric, Date, DateTime, JSON, Boolean, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    return datetime.now(timezone.utc)

class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class Role(Base):
    __tablename__ = 'roles'
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    permissions: Mapped[list] = mapped_column(JSON, default=list)

class User(Record, Base):
    __tablename__ = 'users'
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(250), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(ForeignKey('roles.name'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Session(Record, Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class LoginAttempt(Record, Base):
    __tablename__ = 'login_attempts'
    key: Mapped[str] = mapped_column(String(64), index=True)

class Supplier(Record, Base):
    __tablename__ = 'suppliers'
    name: Mapped[str] = mapped_column(String(200), index=True)
    registration: Mapped[str] = mapped_column(String(100), default='')
    contact: Mapped[str] = mapped_column(String(150), default='')
    email: Mapped[str] = mapped_column(String(250), default='')
    phone: Mapped[str] = mapped_column(String(60), default='')
    address: Mapped[str] = mapped_column(Text, default='')
    payment_terms: Mapped[int] = mapped_column(default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Document(Record, Base):
    __tablename__ = 'documents'
    name: Mapped[str] = mapped_column(String(250))
    key: Mapped[str] = mapped_column(String(200), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    category: Mapped[str] = mapped_column(String(30), default='invoice')

class Bill(Record, Base):
    __tablename__ = 'supplier_bills'
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey('suppliers.id'), index=True)
    supplier: Mapped[Supplier | None] = relationship()
    document_id: Mapped[str | None] = mapped_column(ForeignKey('documents.id'), index=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    number: Mapped[str] = mapped_column(String(150), default='', index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    currency: Mapped[str] = mapped_column(String(3), default='MYR')
    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default='needs_review', index=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    duplicate_ids: Mapped[list] = mapped_column(JSON, default=list)
    duplicate_resolution: Mapped[str] = mapped_column(Text, default='')
    verified_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    items: Mapped[list['LineItem']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (CheckConstraint('total >= 0 AND subtotal >= 0 AND tax >= 0'), Index('ix_bill_duplicate', 'supplier_id', 'number'))

class LineItem(Record, Base):
    __tablename__ = 'invoice_line_items'
    bill_id: Mapped[str] = mapped_column(ForeignKey('supplier_bills.id'), index=True)
    description: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(20),default='unit')
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2))

class Payment(Record, Base):
    __tablename__ = 'payments'
    supplier_id: Mapped[str] = mapped_column(ForeignKey('suppliers.id'), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    reference: Mapped[str] = mapped_column(String(150))
    method: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str] = mapped_column(Text, default='')
    allocations: Mapped[list['Allocation']] = relationship(lazy='selectin', cascade='all, delete-orphan')

class Allocation(Record, Base):
    __tablename__ = 'payment_allocations'
    payment_id: Mapped[str] = mapped_column(ForeignKey('payments.id'), index=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey('supplier_bills.id'), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    __table_args__ = (CheckConstraint('amount > 0'), UniqueConstraint('payment_id', 'bill_id'))

class ExpectedInvoice(Record, Base):
    __tablename__ = 'expected_invoices'
    supplier_id: Mapped[str] = mapped_column(ForeignKey('suppliers.id'), index=True)
    expected_date: Mapped[date] = mapped_column(Date, index=True)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='expected')
    bill_id: Mapped[str | None] = mapped_column(ForeignKey('supplier_bills.id'))
    resolution: Mapped[str] = mapped_column(Text, default='')

class Employee(Record, Base):
    __tablename__ = 'employees'
    employee_code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    position: Mapped[str] = mapped_column(String(100), default='')
    department: Mapped[str] = mapped_column(String(100), default='')
    email: Mapped[str] = mapped_column(String(250), default='')
    phone: Mapped[str] = mapped_column(String(60), default='')
    start_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    salary: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    bank_name: Mapped[str] = mapped_column(String(150), default='')
    bank_account: Mapped[str] = mapped_column(String(100), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (CheckConstraint('salary >= 0'),)

class Payroll(Record, Base):
    __tablename__ = 'payroll'
    period: Mapped[str] = mapped_column(String(7), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey('employees.id'), index=True)
    employee_name: Mapped[str] = mapped_column(String(150))
    employee_code: Mapped[str] = mapped_column(String(40))
    basic: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    allowances: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    overtime: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    deductions: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    payment_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint('period', 'employee_id'), CheckConstraint('basic + allowances + overtime >= deductions'))

class Audit(Record, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    actor_name: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

class Job(Record, Base):
    __tablename__ = 'processing_jobs'
    bill_id: Mapped[str] = mapped_column(ForeignKey('supplier_bills.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(String(300), default='')

class BusinessSetting(Base):
    __tablename__ = 'business_settings'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
