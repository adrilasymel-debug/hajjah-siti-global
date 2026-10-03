from datetime import datetime
from sqlalchemy import select
from app import people
from app.models import Audit, Overtime


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 4, 20, 0, tzinfo=tz)


def test_staff_submit_own_overtime_and_boss_approves(ctx, monkeypatch):
    monkeypatch.setattr(people, 'datetime', FixedDateTime)
    response=ctx['staff'].post('/api/overtime',json={
        'start_time':'18:00','end_time':'19:30','break_minutes':15,
        'reason':'Packed the urgent dried seafood delivery order.'
    })
    assert response.status_code==201,response.text
    item=response.json()
    assert item['staff_name']=='staff'
    assert item['work_date']=='2026-10-04'
    assert item['minutes']==75
    assert item['status']=='submitted'

    own=ctx['staff'].get('/api/overtime').json()
    assert own['today']=='2026-10-04'
    assert [record['id'] for record in own['items']]==[item['id']]
    assert ctx['other'].get('/api/overtime').json()['items']==[]
    assert ctx['staff'].post(f"/api/overtime/{item['id']}/approve").status_code==403

    boss_items=ctx['boss'].get('/api/overtime?status=submitted').json()['items']
    assert [record['id'] for record in boss_items]==[item['id']]
    approved=ctx['boss'].post(f"/api/overtime/{item['id']}/approve")
    assert approved.status_code==200
    assert approved.json()['status']=='approved'
    with ctx['db']() as db:
        assert db.scalar(select(Audit).where(Audit.action=='overtime_submitted'))
        assert db.scalar(select(Audit).where(Audit.action=='overtime_approved'))


def test_overtime_rejects_backdating_future_and_duplicate_periods(ctx, monkeypatch):
    monkeypatch.setattr(people, 'datetime', FixedDateTime)
    base={'start_time':'18:00','end_time':'19:00','break_minutes':0,'reason':'Completed an urgent stock count.'}
    backdated=ctx['staff'].post('/api/overtime',json={**base,'work_date':'2026-10-03'})
    assert backdated.status_code==422
    future=ctx['staff'].post('/api/overtime',json={**base,'end_time':'20:30'})
    assert future.status_code==422
    crossing_midnight=ctx['staff'].post('/api/overtime',json={**base,'start_time':'23:00','end_time':'01:00'})
    assert crossing_midnight.status_code==422

    created=ctx['staff'].post('/api/overtime',json=base)
    assert created.status_code==201
    assert ctx['staff'].post('/api/overtime',json=base).status_code==409
    rejected=ctx['boss'].post(f"/api/overtime/{created.json()['id']}/reject",json={'reason':'Hours cannot be confirmed.'})
    assert rejected.status_code==200
    assert rejected.json()['status']=='rejected'
    assert ctx['staff'].post('/api/overtime',json=base).status_code==201
