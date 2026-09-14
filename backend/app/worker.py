import logging
import time
from datetime import timedelta
from sqlalchemy import select, or_, and_
from .db import SessionLocal
from .models import Job, Bill, Document, now
from .processing import extract_text, extract_structured, ProcessingUnavailable
from .storage import storage
from .services import apply_bill, detect_duplicates
from .security import audit

log=logging.getLogger(__name__)

def run_once():
    with SessionLocal() as db:
        job=db.scalar(select(Job).where(or_(Job.status=='queued',and_(Job.status=='running',Job.locked_at<now()-timedelta(minutes=10)))).order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job:return False
        job.status='running';job.locked_at=now();job.attempts+=1
        job_id,bill_id,attempt=job.id,job.bill_id,job.attempts
        bill=db.get(Bill,bill_id);doc=db.get(Document,bill.document_id);key,mime=doc.key,doc.mime;db.commit()
    try:
        if attempt>3:raise ProcessingUnavailable('Processing stopped after repeated interruptions. Review this invoice manually or retry.')
        data=storage.get(key)
        from .config import settings
        if settings.extraction_provider=='gemini':
            from .gemini import extract_document
            extracted,review=extract_document(data,mime)
        else:
            text=extract_text(data,mime,key);extracted,review=extract_structured(text)
        with SessionLocal() as db:
            job=db.scalar(select(Job).where(Job.id==job_id).with_for_update())
            if job.attempts!=attempt:return True
            bill=db.scalar(select(Bill).where(Bill.id==bill_id).with_for_update())
            if bill.status!='processing':job.status='cancelled';db.commit();return True
            apply_bill(db,bill,extracted);bill.review=review;bill.status='needs_review';bill.version+=1
            db.flush();detect_duplicates(db,bill);job.status='completed';audit(db,None,'invoice_processed','bill',bill_id,{'provider_model':settings_model(),'human_review_required':True});db.commit()
    except Exception as exc:
        message=str(exc) if isinstance(exc,ProcessingUnavailable) else 'Unable to process this invoice automatically. Your document is safe; review it manually or retry.'
        log.warning('Invoice processing failed for job %s (%s)',job_id,type(exc).__name__)
        with SessionLocal() as db:
            job=db.scalar(select(Job).where(Job.id==job_id).with_for_update())
            if job.attempts!=attempt:return True
            job.status='failed';job.error=message
            bill=db.scalar(select(Bill).where(Bill.id==bill_id).with_for_update())
            if bill.status=='processing':bill.status='processing_failed';bill.review={'message':message};bill.version+=1
            audit(db,None,'invoice_processing_failed','bill',bill_id,{'message':message});db.commit()
    return True

def settings_model():
    from .config import settings
    return settings.gemini_model if settings.extraction_provider=='gemini' else settings.extraction_model

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if not run_once():time.sleep(3)
        except Exception:
            log.exception('Worker could not claim job');time.sleep(5)
