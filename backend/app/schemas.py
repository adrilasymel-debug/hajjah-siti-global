from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

Money = Decimal
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)

class LoginIn(Input):
    email: str = Field(max_length=250)
    password: str = Field(max_length=200)

class UserIn(Input):
    name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=250, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=72)
    role: Literal['BOSS', 'STAFF']

class SupplierIn(Input):
    name: str = Field(min_length=2, max_length=200)
    registration: str = Field(default='', max_length=100)
    contact: str = Field(default='', max_length=150)
    email: str = Field(default='', max_length=250)
    phone: str = Field(default='', max_length=60)
    address: str = Field(default='', max_length=2000)
    payment_terms: int = Field(default=30, ge=0, le=365)
    active: bool = True
    notes: str = Field(default='', max_length=5000)

class ItemIn(Input):
    description: str = Field(min_length=1, max_length=500)
    unit: str = Field(default='unit',min_length=1,max_length=20)
    quantity: Decimal = Field(gt=0, le=1000000, decimal_places=3)
    unit_price: Decimal = Field(ge=0, le=100000000, decimal_places=2)
    tax: Decimal = Field(default=0, ge=0, decimal_places=2)
    total: Decimal = Field(ge=0, decimal_places=2)

class BillIn(Input):
    supplier_id: str | None = None
    number: str = Field(default='', max_length=150)
    invoice_date: date | None = None
    due_date: date | None = None
    currency: Literal['MYR'] = 'MYR'
    subtotal: Decimal = Field(default=0, ge=0, le=1000000000, decimal_places=2)
    tax: Decimal = Field(default=0, ge=0, le=1000000000, decimal_places=2)
    total: Decimal = Field(default=0, ge=0, le=1000000000, decimal_places=2)
    notes: str = Field(default='', max_length=5000)
    items: list[ItemIn] = Field(default_factory=list, max_length=500)

class BillCreate(BillIn):
    supplier_name: str | None = Field(default=None,min_length=2,max_length=200)

    @model_validator(mode='after')
    def supplier_choice(self):
        if self.supplier_id and self.supplier_name:
            raise ValueError('Choose an existing supplier or enter a new name, not both')
        return self

class BillEdit(BillCreate):
    version: int = Field(ge=1)

class VerifyIn(Input):
    version: int
    duplicate_resolution: str = Field(default='', max_length=2000)

class ReasonIn(Input):
    reason: str = Field(min_length=5, max_length=2000)

class AllocationIn(Input):
    bill_id: str
    amount: Decimal = Field(gt=0, le=1000000000, decimal_places=2)

class PaymentIn(Input):
    supplier_id: str
    payment_date: date
    reference: str = Field(min_length=1, max_length=150)
    method: Literal['bank_transfer', 'cash', 'cheque', 'card'] = 'bank_transfer'
    notes: str = Field(default='', max_length=5000)
    idempotency_key: str = Field(min_length=10, max_length=100)
    allocations: list[AllocationIn] = Field(min_length=1, max_length=100)
    @model_validator(mode='after')
    def unique_bills(self):
        if len({a.bill_id for a in self.allocations}) != len(self.allocations):
            raise ValueError('Allocate to each bill only once')
        if self.payment_date > date.today():
            raise ValueError('Payment date cannot be in the future')
        return self

class ExpectedIn(Input):
    supplier_id: str
    expected_date: date
    evidence: str = Field(min_length=5, max_length=2000)

class ResolveIn(Input):
    status: Literal['resolved', 'exempted']
    bill_id: str | None = None
    resolution: str = Field(min_length=5, max_length=2000)

class EmployeeIn(Input):
    employee_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=150)
    position: str = Field(default='', max_length=100)
    department: str = Field(default='', max_length=100)
    email: str = Field(default='', max_length=250)
    phone: str = Field(default='', max_length=60)
    start_date: date
    active: bool = True
    salary: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    bank_name: str = Field(default='', max_length=150)
    bank_account: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=5000)

class PayrollIn(Input):
    period: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    employee_id: str
    allowances: Decimal = Field(default=0, ge=0, le=10000000, decimal_places=2)
    overtime: Decimal = Field(default=0, ge=0, le=10000000, decimal_places=2)
    deductions: Decimal = Field(default=0, ge=0, le=10000000, decimal_places=2)

class PayrollPayIn(Input):
    payment_date: date
    @field_validator('payment_date')
    @classmethod
    def past(cls, value):
        if value > date.today(): raise ValueError('Payment date cannot be in the future')
        return value

class SettingIn(Input):
    company_name: str = Field(min_length=2, max_length=150)

class UserAccessIn(Input):
    role: Literal['BOSS', 'STAFF']
    active: bool

class PasswordIn(Input):
    current_password: str
    new_password: str = Field(min_length=12, max_length=72)
