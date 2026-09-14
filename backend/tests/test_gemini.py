import base64
import json
import httpx
import pytest
from app.config import settings
from app.gemini import extract_document
from app.processing import ProcessingUnavailable

@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setattr(settings,'gemini_api_key','test-key')
    monkeypatch.setattr(settings,'gemini_free_tier_confirmed',True)
    monkeypatch.setattr(settings,'free_only',True)
    monkeypatch.setattr(settings,'gemini_model','gemini-3.6-flash')

def mock_provider(monkeypatch,handler):
    original=httpx.Client
    monkeypatch.setattr('app.gemini.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))

@pytest.mark.parametrize('mime',['application/pdf','image/png','image/jpeg'])
def test_cloud_vision_receives_original_and_requires_review(cloud,monkeypatch,mime):
    def provider(request):
        assert request.url.host=='generativelanguage.googleapis.com'
        assert request.headers['x-goog-api-key']=='test-key'
        body=json.loads(request.content)
        inline=body['contents'][0]['parts'][0]['inlineData']
        assert inline['mimeType']==mime and base64.b64decode(inline['data'])==b'original'
        assert 'tools' not in body
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'supplier_name':'Seafood Supply','invoice':{'supplier_id':'untrusted-id','number':'A123','subtotal':'100','total':'100'}})}]}}]})
    mock_provider(monkeypatch,provider)
    bill,review=extract_document(b'original',mime)
    assert bill.number=='A123' and bill.supplier_id is None
    assert review['total']['requires_review'] and review['supplier_name']=='Seafood Supply'
    assert review['method']=='gemini_cloud'

@pytest.mark.parametrize('status',[400,401,403,404,429,500])
def test_provider_errors_are_safe(cloud,monkeypatch,status):
    mock_provider(monkeypatch,lambda r:httpx.Response(status,json={'error':'secret-provider-details'}))
    with pytest.raises(ProcessingUnavailable) as exc:extract_document(b'original','image/png')
    assert 'secret-provider-details' not in str(exc.value)

def test_free_tier_confirmation_and_key_required(cloud,monkeypatch):
    monkeypatch.setattr(settings,'gemini_free_tier_confirmed',False)
    with pytest.raises(ProcessingUnavailable):extract_document(b'x','image/png')
    monkeypatch.setattr(settings,'gemini_free_tier_confirmed',True)
    monkeypatch.setattr(settings,'gemini_api_key','')
    with pytest.raises(ProcessingUnavailable):extract_document(b'x','image/png')

def test_truncated_response_is_not_used(cloud,monkeypatch):
    mock_provider(monkeypatch,lambda r:httpx.Response(200,json={'candidates':[{'finishReason':'MAX_TOKENS'}]}))
    with pytest.raises(ProcessingUnavailable):extract_document(b'x','image/png')

def test_staff_library_denied_but_own_invoice_review_allowed(ctx):
    from tests.test_processing import upload
    bill=upload(ctx)
    assert ctx['staff'].get('/api/documents').status_code==403
    assert ctx['boss'].get('/api/documents').status_code==200
    assert ctx['staff'].get('/api/supplier-bills/'+bill['id']).status_code==200
    assert ctx['staff'].get('/api/documents/'+bill['document_id']+'/content').status_code==200
    assert ctx['other'].get('/api/documents/'+bill['document_id']+'/content').status_code==404
    assert ctx['other'].get('/api/supplier-bills').json()['total']==0

def test_worker_uses_cloud_without_local_ocr(ctx,cloud,monkeypatch):
    from tests.test_processing import upload
    from app import worker
    from app.schemas import BillIn
    bill=upload(ctx)
    monkeypatch.setattr(settings,'extraction_provider','gemini')
    monkeypatch.setattr(worker,'SessionLocal',ctx['db'])
    def no_local(*args):raise AssertionError('Local OCR must not run')
    monkeypatch.setattr(worker,'extract_text',no_local)
    monkeypatch.setattr('app.gemini.extract_document',lambda *args:(BillIn(number='CLOUD'),{'method':'gemini_cloud'}))
    assert worker.run_once()
    detail=ctx['staff'].get('/api/supplier-bills/'+bill['id']).json()
    assert detail['number']=='CLOUD' and detail['status']=='needs_review' and detail['verified_at'] is None
