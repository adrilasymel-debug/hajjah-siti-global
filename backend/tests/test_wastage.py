import io
import pytest
from PIL import Image
from sqlalchemy import select
from app.models import Audit, Wastage

def photo(color='red'):
    out=io.BytesIO();Image.new('RGB',(20,20),color).save(out,format='PNG');return out.getvalue()

def report(ctx, **overrides):
    data={'goods_name':'Ikan bilis','damage_date':'2026-01-01','quantity_kg':'2.350','damage':'Moisture and visible mould'}
    data.update(overrides)
    return ctx['staff'].post('/api/wastage',data=data,files=[('photos',('damage.png',photo(),'image/png'))])

def instruct(ctx,row,action='dispose'):
    return ctx['boss'].post('/api/wastage/'+row['id']+'/decision',json={'version':row['version'],'action':action,'instruction':'Discard safely and photograph the cleared area.'})

def proof(ctx,row,color='blue',actor='staff'):
    return ctx[actor].post('/api/wastage/'+row['id']+'/proof',data={'version':row['version'],'note':'Disposed of goods in the waste area today.'},files=[('photos',('proof.png',photo(color),'image/png'))])

@pytest.mark.parametrize('action',['dispose','keep','other'])
def test_complete_workflow_and_notifications(ctx,action):
    response=report(ctx);assert response.status_code==201,response.text
    row=response.json();id=row['id'];assert row['staff_name']=='staff';assert row['quantity_kg']==2.35
    assert ctx['boss'].get('/api/notifications').json()['unread']==1
    decision=instruct(ctx,row,action);assert decision.status_code==200,decision.text
    row=decision.json();assert row['status']=='action_required'
    assert ctx['staff'].get('/api/notifications').json()['unread']==1
    response=proof(ctx,row);assert response.status_code==200,response.text
    row=response.json();assert row['status']=='proof_submitted'
    response=ctx['boss'].post('/api/wastage/'+id+'/review',json={'version':row['version'],'outcome':'accept','remark':'Evidence shows the required action was completed.'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='completed'
    detail=ctx['staff'].get('/api/wastage/'+id).json()
    assert len(detail['evidence'])==2
    assert [h['action'] for h in detail['history']]==['wastage_reported','wastage_instructed','wastage_proof_submitted','wastage_completed']
    assert proof(ctx,response.json(),color='green').status_code==409

def test_access_and_workflow_guards(ctx):
    row=report(ctx).json();path='/api/wastage/'+row['id']
    assert ctx['other'].get('/api/wastage').json()['items']==[]
    assert ctx['other'].get(path).status_code==404
    d=ctx['staff'].get(path).json()['evidence'][0]['document_id']
    assert ctx['staff'].get('/api/documents/'+d+'/content').status_code==200
    assert ctx['boss'].get('/api/documents/'+d+'/content').status_code==200
    assert ctx['other'].get('/api/documents/'+d+'/content').status_code==404
    assert ctx['staff'].post(path+'/decision',json={'version':1,'action':'dispose','instruction':'Throw away safely'}).status_code==403
    assert proof(ctx,row).status_code==409
    row=instruct(ctx,row).json()
    assert instruct(ctx,row).status_code==409
    assert proof(ctx,row,actor='boss').status_code==403
    assert proof(ctx,row,color='red').status_code==422
    row=proof(ctx,row).json()
    assert ctx['staff'].post(path+'/review',json={'version':row['version'],'outcome':'accept','remark':'Looks correct'}).status_code==403
    n=ctx['staff'].get('/api/notifications').json()['items'][0]
    assert ctx['other'].post('/api/notifications/'+n['id']+'/read').status_code==404
    assert ctx['staff'].post('/api/notifications/'+n['id']+'/read').status_code==200
    assert ctx['staff'].get('/api/notifications').json()['unread']==0

def test_returned_evidence_is_preserved_and_stale_review_rejected(ctx):
    row=proof(ctx,instruct(ctx,report(ctx).json()).json()).json();path='/api/wastage/'+row['id']
    response=ctx['boss'].post(path+'/review',json={'version':row['version'],'outcome':'request_more','remark':'Show the cleared storage area too.'})
    assert response.status_code==200
    assert ctx['boss'].post(path+'/review',json={'version':row['version'],'outcome':'accept','remark':'Stale browser review'}).status_code==409
    row=response.json();assert proof(ctx,row).status_code==422
    row=proof(ctx,row,color='green').json()
    assert len(ctx['staff'].get(path).json()['evidence'])==3
    assert row['status']=='proof_submitted'

@pytest.mark.parametrize('bad',[{'quantity_kg':'0'},{'quantity_kg':'-1'},{'quantity_kg':'1.0001'},{'goods_name':' '},{'damage':' '},{'damage_date':'2099-01-01'}])
def test_report_validation(ctx,bad):
    assert report(ctx,**bad).status_code==422
    assert ctx['boss'].get('/api/wastage').json()['total']==0

def test_fake_photo_rejected_without_record(ctx):
    response=ctx['staff'].post('/api/wastage',data={'goods_name':'Fish','damage_date':'2026-01-01','quantity_kg':'1','damage':'Broken packaging'},files={'photos':('fake.jpg',b'not a photo','image/jpeg')})
    assert response.status_code==422
    with ctx['db']() as db: assert db.scalar(select(Wastage)) is None
