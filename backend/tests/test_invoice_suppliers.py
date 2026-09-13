from datetime import date
from sqlalchemy import select,func
from app.models import Supplier,Audit

def payload(name='Pantai Dried Seafood'):
    return {'supplier_name':name,'number':'SEA-001','invoice_date':str(date.today()),'due_date':str(date.today()),'subtotal':'100','tax':'0','total':'100'}

def test_staff_adds_supplier_while_saving_and_can_reuse_it(ctx):
    c=ctx['staff'];r=c.post('/api/supplier-bills',json=payload());assert r.status_code==201,r.text
    b=r.json();assert b['supplier_name']=='Pantai Dried Seafood'
    assert c.post('/api/supplier-bills/'+b['id']+'/verify',json={'version':b['version']}).status_code==200
    r=c.post('/api/supplier-bills',json={**payload(' pantai dried seafood '),'number':'SEA-002'})
    assert r.status_code==201 and r.json()['supplier_id']==b['supplier_id']
    assert any(s['id']==b['supplier_id'] for s in c.get('/api/suppliers/lookup?q=Pantai').json())
    with ctx['db']() as db:
        assert db.scalar(select(func.count()).select_from(Supplier))==1
        events=list(db.scalars(select(Audit).where(Audit.action=='supplier_created')))
        assert len(events)==1 and events[0].details['source']=='invoice_review'
    assert c.post('/api/suppliers',json={'name':'Forbidden directory creation'}).status_code==403

def test_review_can_add_new_names_repeatedly_without_changing_old_suppliers(ctx):
    c=ctx['staff'];b=c.post('/api/supplier-bills',json=payload()).json()
    for name in ['New Seafood Supplier','Another Seafood Supplier']:
        r=c.put('/api/supplier-bills/'+b['id'],json={**payload(name),'version':b['version']})
        assert r.status_code==200,r.text;b=r.json()
        assert b['supplier_name']==name
    with ctx['db']() as db:assert db.scalar(select(func.count()).select_from(Supplier))==3

def test_forbidden_or_stale_edits_do_not_create_supplier(ctx):
    c=ctx['staff'];b=c.post('/api/supplier-bills',json=payload()).json()
    for who,version,status in [('other',b['version'],404),('staff',b['version']+1,409)]:
        r=ctx[who].put('/api/supplier-bills/'+b['id'],json={**payload('Must Not Be Created'),'version':version})
        assert r.status_code==status,r.text
    with ctx['db']() as db:assert db.scalar(select(func.count()).select_from(Supplier))==1
    assert c.post('/api/supplier-bills',json={**payload(),'supplier_id':b['supplier_id']}).status_code==422
    assert c.post('/api/supplier-bills',json=payload(' ')).status_code==422

def test_inactive_supplier_is_not_recreated(ctx):
    supplier=ctx['boss'].post('/api/suppliers',json={'name':'Inactive Seafood','active':False}).json()
    r=ctx['staff'].post('/api/supplier-bills',json=payload('inactive seafood'))
    assert r.status_code==422 and 'inactive' in r.json()['detail']
    with ctx['db']() as db:assert db.scalar(select(func.count()).select_from(Supplier))==1
