from io import BytesIO
from PIL import Image
from sqlalchemy import select
from app.config import settings
from app.models import Audit, Bill, Document


def invoice(client, number='REMOVE-001'):
    response=client.post('/api/supplier-bills',json={
        'supplier_name':'Removal Test Seafood',
        'number':number,
        'invoice_date':'2026-09-20',
        'due_date':None,
        'subtotal':'25.00','tax':'0.00','total':'25.00','items':[]
    })
    assert response.status_code==201,response.text
    return response.json()


def test_archive_is_owner_only_hidden_and_recoverable(ctx):
    bill=invoice(ctx['staff'])
    assert ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/reject',json={'reason':'Wrong document uploaded'}).status_code==200
    assert ctx['staff'].post('/api/supplier-bills/'+bill['id']+'/archive',json={'reason':'Remove rejected upload'}).status_code==403

    archived=ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/archive',json={'reason':'Remove rejected upload'})
    assert archived.status_code==200,archived.text
    assert archived.json()['archive_reason']=='Remove rejected upload'
    assert ctx['boss'].get('/api/supplier-bills').json()['total']==0
    archive_list=ctx['boss'].get('/api/supplier-bills?archived=true').json()
    assert archive_list['total']==1 and archive_list['items'][0]['id']==bill['id']
    assert ctx['staff'].get('/api/supplier-bills?archived=true').status_code==403
    assert ctx['staff'].get('/api/supplier-bills/'+bill['id']).status_code==404

    restored=ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/restore',json={})
    assert restored.status_code==200 and restored.json()['archived_at'] is None
    assert ctx['boss'].get('/api/supplier-bills').json()['total']==1


def test_official_invoice_cannot_be_archived(ctx):
    bill=invoice(ctx['staff'],'KEEP-001')
    verified=ctx['staff'].post('/api/supplier-bills/'+bill['id']+'/verify',json={'version':bill['version']})
    assert verified.status_code==200,verified.text
    blocked=ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/archive',json={'reason':'Should not disappear'})
    assert blocked.status_code==409


def test_previously_verified_invoice_can_never_be_permanently_deleted(ctx):
    bill=invoice(ctx['staff'],'OFFICIAL-001')
    verified=ctx['staff'].post('/api/supplier-bills/'+bill['id']+'/verify',json={'version':bill['version']})
    assert verified.status_code==200,verified.text
    assert ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/reject',json={'reason':'Supplier cancelled invoice'}).status_code==200
    assert ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/archive',json={'reason':'Cancelled official record'}).status_code==200
    blocked=ctx['boss'].post('/api/supplier-bills/'+bill['id']+'/delete',json={'reason':'Attempt to erase official record'})
    assert blocked.status_code==409
    assert 'official financial history' in blocked.json()['detail']


def test_permanent_delete_requires_archive_and_removes_document(ctx):
    image=BytesIO();Image.new('RGB',(40,40),'white').save(image,format='PNG')
    uploaded=ctx['staff'].post('/api/supplier-bills/upload',files={'file':('mistake.png',image.getvalue(),'image/png')})
    assert uploaded.status_code==201,uploaded.text
    bill_id=uploaded.json()['id']
    with ctx['db']() as db:
        bill=db.get(Bill,bill_id);bill.status='processing_failed';document=db.get(Document,bill.document_id)
        object_path=document.key;db.commit()

    assert ctx['boss'].post('/api/supplier-bills/'+bill_id+'/delete',json={'reason':'Accidental upload'}).status_code==409
    assert ctx['boss'].post('/api/supplier-bills/'+bill_id+'/archive',json={'reason':'Accidental failed upload'}).status_code==200
    deleted=ctx['boss'].post('/api/supplier-bills/'+bill_id+'/delete',json={'reason':'Confirmed accidental upload'})
    assert deleted.status_code==200,deleted.text
    assert ctx['boss'].get('/api/supplier-bills/'+bill_id).status_code==404
    assert not (settings.storage_path/object_path).exists()

    with ctx['db']() as db:
        assert db.get(Bill,bill_id) is None
        assert db.scalar(select(Document).where(Document.key==object_path)) is None
        event=db.scalar(select(Audit).where(Audit.action=='invoice_deleted',Audit.entity_id==bill_id))
        assert event and event.details['document_name']=='mistake.png'
