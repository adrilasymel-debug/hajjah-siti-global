from io import BytesIO
from PIL import Image
from sqlalchemy import select
from app.models import Job,Bill,Audit
from app import worker
from app.schemas import BillIn

def upload(ctx):
    out=BytesIO();Image.new('RGB',(80,80),'white').save(out,'PNG')
    r=ctx['staff'].post('/api/supplier-bills/upload',files={'file':('invoice.png',out.getvalue(),'image/png')});assert r.status_code==201;return r.json()

def test_ocr_failure_preserves_document_and_manual_review(ctx,monkeypatch):
    b=upload(ctx);monkeypatch.setattr(worker,'SessionLocal',ctx['db'])
    def fail(*args):raise RuntimeError('provider secret must never reach response')
    monkeypatch.setattr(worker,'extract_text',fail);assert worker.run_once()
    detail=ctx['staff'].get('/api/supplier-bills/'+b['id']).json();assert detail['status']=='processing_failed'
    assert 'secret' not in detail['review']['message']
    assert ctx['staff'].get('/api/documents/'+b['document_id']+'/content').status_code==200
    assert ctx['staff'].post('/api/supplier-bills/'+b['id']+'/retry').status_code==200

def test_ai_output_remains_unverified(ctx,monkeypatch):
    b=upload(ctx);monkeypatch.setattr(worker,'SessionLocal',ctx['db'])
    monkeypatch.setattr(worker,'extract_text',lambda *args:'untrusted invoice text')
    monkeypatch.setattr(worker,'extract_structured',lambda text:(BillIn(number='AI-123',subtotal=100,total=100),{'total':{'requires_review':True,'confidence':None}}))
    assert worker.run_once();detail=ctx['staff'].get('/api/supplier-bills/'+b['id']).json()
    assert detail['status']=='needs_review';assert detail['verified_at'] is None;assert detail['number']=='AI-123'
    assert detail['review']['total']['requires_review']

def test_oversize_empty_image_and_active_pdf_rejected(ctx):
    c=ctx['staff']
    for name,body,mime in [('empty.png',b'','image/png'),('fake.jpg',b'not an image','image/jpeg'),('active.pdf',b'%PDF-1.4 /JavaScript','application/pdf')]:
        assert c.post('/api/supplier-bills/upload',files={'file':(name,body,mime)}).status_code==422
    assert c.post('/api/supplier-bills/upload',files={'file':('large.png',b'x'*(15*1024*1024+1),'image/png')}).status_code==422
