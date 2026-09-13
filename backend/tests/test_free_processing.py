from decimal import Decimal
import pytest
from app.config import settings
from app.processing import extract_structured,extract_text,ProcessingUnavailable
from app.rule_extraction import extract

def test_free_rules_preserve_amounts_dates_and_human_review():
    bill,review=extract('Invoice No: HSG-0088\nInvoice Date: 13/09/2026\nDue Date: 13/10/2026\nSubtotal: RM 1,750.25\nTax: RM 0.00\nGrand Total: RM 1,750.25')
    assert bill.number=='HSG-0088'
    assert str(bill.invoice_date)=='2026-09-13'
    assert str(bill.due_date)=='2026-10-13'
    assert bill.total==Decimal('1750.25') and bill.tax==0
    assert bill.supplier_id is None and not review['ai_used']
    assert review['total']['requires_review'] and review['total']['confidence'] is None

def test_free_rules_do_not_invent_missing_values_or_accept_foreign_currency():
    bill,_=extract('DRIED ANCHOVIES SUPPLIER')
    assert bill.number=='' and bill.invoice_date is None and bill.total==0
    for text in ['', 'Invoice No: ABC-0088\nTotal: USD 100.00']:
        with pytest.raises(ValueError):extract(text)

def test_free_mode_blocks_external_ocr_and_ai(monkeypatch):
    monkeypatch.setattr(settings,'free_only',True)
    monkeypatch.setattr(settings,'ocr_provider','textract')
    with pytest.raises(ProcessingUnavailable):extract_text(b'image','image/png')
    monkeypatch.setattr(settings,'extraction_provider','api')
    with pytest.raises(ProcessingUnavailable):extract_structured('private invoice')
    monkeypatch.setattr(settings,'extraction_provider','ollama')
    monkeypatch.setattr(settings,'extraction_endpoint','https://external.example/api/chat')
    monkeypatch.setattr(settings,'extraction_model','local-model')
    with pytest.raises(ProcessingUnavailable):extract_structured('private invoice')

def test_local_rules_run_through_processing_pipeline(ctx,monkeypatch):
    from io import BytesIO
    from PIL import Image
    from app import worker
    out=BytesIO();Image.new('RGB',(80,80),'white').save(out,'PNG')
    response=ctx['staff'].post('/api/supplier-bills/upload',files={'file':('invoice.png',out.getvalue(),'image/png')})
    assert response.status_code==201
    b=response.json()
    monkeypatch.setattr(worker,'SessionLocal',ctx['db'])
    monkeypatch.setattr(settings,'extraction_provider','rules')
    monkeypatch.setattr(worker,'extract_text',lambda *args:'Invoice No: SEA-0088\nSubtotal: RM 750.00\nGrand Total: RM 750.00')
    assert worker.run_once()
    detail=ctx['staff'].get('/api/supplier-bills/'+b['id']).json()
    assert detail['status']=='needs_review' and detail['verified_at'] is None
    assert detail['number']=='SEA-0088' and detail['review']['method']=='local_ocr_rules'
