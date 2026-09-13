from decimal import Decimal
from .test_workflows import verified,payment

def test_void_payment_restores_balance_without_erasing_history(ctx):
    b=verified(ctx);p=payment(ctx,b).json();c=ctx['boss']
    assert ctx['staff'].post('/api/payments/'+p['id']+'/void',json={'reason':'Incorrect allocation'}).status_code==403
    r=c.post('/api/payments/'+p['id']+'/void',json={'reason':'Bank transfer was returned by the supplier bank'})
    assert r.status_code==200,r.text
    assert c.post('/api/payments/'+p['id']+'/void',json={'reason':'Second void attempt'}).status_code==409
    detail=c.get('/api/supplier-bills/'+b['id']).json();assert Decimal(detail['outstanding'])==106
    assert detail['payments'][0]['voided']
    assert Decimal(c.get('/api/dashboard').json()['outstanding'])==106
    assert Decimal(c.get('/api/reports').json()['suppliers'][0]['paid'])==0
