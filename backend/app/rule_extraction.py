"""Conservative, free field suggestions. These are rules, not an AI model."""
import re
from datetime import date
from decimal import Decimal
from .schemas import BillIn

def extract(text):
    if not text.strip():raise ValueError('No readable document text')
    if re.search(r'\b(?:USD|SGD|THB|IDR|EUR|GBP|CNY|RMB)\b',text,re.I):
        raise ValueError('Foreign currency requires manual review; this business currently records MYR only')
    def amount(pattern):
        matches=re.findall(pattern+r'\s*[:\-]?\s*(?:RM|MYR)?\s*([\d,]+\.\d{2})',text,re.I)
        return Decimal(matches[-1].replace(',','')) if matches else None
    def date_field(pattern):
        match=re.search(pattern+r'\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})',text,re.I)
        if not match:return None
        raw=match.group(1)
        try:
            if re.match(r'\d{4}-',raw):return date.fromisoformat(raw)
            day,month,year=map(int,re.split(r'[/.\-]',raw));return date(year,month,day)
        except ValueError:return None
    number=re.search(r'(?:invoice\s*(?:no\.?|number|#)|no\.?\s*invois)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/._-]{2,80})',text,re.I)
    if not number:number=re.search(r'\b([A-Z]{2,8}[-/]\d{2,4}[-/]\d{2,10})\b',text)
    subtotal=amount(r'\bsub\s*total');tax=amount(r'\b(?:tax|sst|cukai)(?:\s*\([^)]*\))?')
    total=amount(r'\b(?:grand\s+total|total\s+(?:amount|due)|jumlah\s*(?:besar|keseluruhan))')
    if total is None:total=amount(r'(?<!sub)\btotal')
    fields={'number':number.group(1) if number else '', 'invoice_date':date_field(r'(?:invoice\s+date|tarikh\s+invois|(?<!due\s)date)'), 'due_date':date_field(r'(?:due\s+date|tarikh\s+akhir)'), 'subtotal':subtotal or Decimal(0), 'tax':tax or Decimal(0), 'total':total or Decimal(0)}
    review={key:{'requires_review':True,'confidence':None,'suggested':value not in [None,'',Decimal(0)]} for key,value in fields.items()}
    review.update(method='local_ocr_rules',ai_used=False,source_text=text[:100000],message='Document text read using free tools. Fields are rule-based suggestions, not AI results. Match the supplier and check every amount and date.')
    return BillIn(**fields),review
