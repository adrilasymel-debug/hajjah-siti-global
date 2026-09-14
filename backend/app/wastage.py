"""Damage reporting and evidence review. All mutations are auditable and versioned."""
import hashlib
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import Wastage, WastageEvidence, Document, Notification, User, Audit, now
from .security import current_user, audit
from .services import columns, page
from .storage import storage, validate_file
from .config import settings

router = APIRouter(tags=['Wastage'])

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    action: Literal['dispose', 'keep', 'other']
    instruction: str = Field(min_length=5, max_length=3000)

class Review(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    outcome: Literal['accept', 'request_more']
    remark: str = Field(min_length=5, max_length=3000)

def boss(user=Depends(current_user)):
    if user.role != 'BOSS': raise HTTPException(403, 'Only the Boss can give instructions or accept evidence')
    return user

def get_record(db, user, id, lock=False):
    query = select(Wastage).where(Wastage.id == id)
    if lock: query = query.with_for_update()
    row = db.scalar(query)
    if not row or (user.role != 'BOSS' and row.submitted_by != user.id):
        raise HTTPException(404, 'Wastage record not found')
    return row

def check_version(row, version, status):
    if row.version != version or row.status != status:
        raise HTTPException(409, 'This record changed. Reload and check its current status.')

def notify(db, row, title, owners=False):
    recipients = list(db.scalars(select(User.id).where(User.role == 'BOSS', User.active == True))) if owners else [row.submitted_by]
    for id in recipients: db.add(Notification(user_id=id, title=title[:250], wastage_id=row.id))

async def read_photos(files):
    if not 1 <= len(files) <= 5: raise HTTPException(422, 'Attach 1 to 5 JPG or PNG photos')
    photos = []; total = 0; hashes = set()
    for file in files:
        content = await file.read(settings.upload_limit_mb * 1024 * 1024 + 1)
        total += len(content)
        if total > settings.upload_limit_mb * 1024 * 1024: raise HTTPException(422, 'Photos must total 15 MB or less')
        mime = validate_file(content)
        if mime not in ['image/jpeg', 'image/png']: raise HTTPException(422, 'Wastage evidence must be JPG or PNG photos')
        digest = hashlib.sha256(content).hexdigest()
        if digest in hashes: raise HTTPException(422, 'Attach different photos rather than repeating the same photo')
        hashes.add(digest)
        photos.append((content, mime, digest))
    return photos

def store_photos(db, row, user, photos, phase, note=''):
    keys = []
    try:
        for content, mime, digest in photos:
            key = storage.put(content, mime); keys.append(key)
            doc = Document(name=f'{phase}-{row.id[:8]}.{ "png" if mime == "image/png" else "jpg"}', key=key, mime=mime, size=len(content), sha256=digest, owner_id=user.id, category='wastage')
            db.add(doc); db.flush()
            db.add(WastageEvidence(wastage_id=row.id, document_id=doc.id, phase=phase, version=row.version, note=note))
        # Commit metadata, audit and notifications together before returning success.
        db.commit()
    except Exception:
        db.rollback()
        for key in keys:
            try: storage.delete(key)
            except Exception: pass
        raise

@router.get('/wastage')
def listing(q:str='', status:str='', date_from:date|None=None, date_to:date|None=None, page_number:int=Query(1,ge=1), page_size:int=Query(25,ge=1,le=100), user=Depends(current_user), db:Session=Depends(get_db)):
    query = select(Wastage).where(Wastage.goods_name.ilike(f'%{q[:100]}%'))
    if user.role != 'BOSS': query = query.where(Wastage.submitted_by == user.id)
    if status: query = query.where(Wastage.status == status)
    if date_from: query = query.where(Wastage.damage_date >= date_from)
    if date_to: query = query.where(Wastage.damage_date <= date_to)
    rows, total = page(db, query.order_by(Wastage.created_at.desc()), page_number, page_size)
    return {'items':[columns(r) for r in rows], 'total':total}

@router.post('/wastage', status_code=201)
async def create(goods_name:str=Form(min_length=1,max_length=200), damage_date:date=Form(), quantity_kg:Decimal=Form(gt=0,max_digits=16,decimal_places=3), damage:str=Form(min_length=5,max_length=3000), photos:list[UploadFile]=File(), user=Depends(current_user), db:Session=Depends(get_db)):
    if not goods_name.strip() or len(damage.strip()) < 5: raise HTTPException(422, 'Enter the goods name and describe the damage')
    if damage_date > date.today(): raise HTTPException(422, 'Damage date cannot be in the future')
    images = await read_photos(photos)
    row = Wastage(goods_name=goods_name.strip(), damage_date=damage_date, quantity_kg=quantity_kg, damage=damage.strip(), submitted_by=user.id, staff_name=user.name)
    db.add(row); db.flush()
    audit(db,user,'wastage_reported','wastage',row.id,{'goods_name':row.goods_name,'quantity_kg':str(quantity_kg),'damage':row.damage})
    notify(db,row,f'New damage report: {row.goods_name}',owners=True)
    store_photos(db,row,user,images,'damage')
    return columns(row)

@router.get('/wastage/{id}')
def detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row = get_record(db,user,id)
    evidence = db.execute(select(WastageEvidence,Document).join(Document,Document.id==WastageEvidence.document_id).where(WastageEvidence.wastage_id==id).order_by(WastageEvidence.created_at)).all()
    return {**columns(row), 'evidence':[{**columns(e),'sha256':d.sha256} for e,d in evidence], 'history':[columns(a) for a in db.scalars(select(Audit).where(Audit.entity=='wastage',Audit.entity_id==id).order_by(Audit.created_at))]}

@router.post('/wastage/{id}/decision')
def decision(id:str,data:Decision,user=Depends(boss),db:Session=Depends(get_db)):
    row = get_record(db,user,id,True); check_version(row,data.version,'awaiting_decision')
    row.action=data.action; row.instruction=data.instruction; row.decided_by=user.id; row.decided_at=now(); row.status='action_required'; row.version+=1
    audit(db,user,'wastage_instructed','wastage',id,data.model_dump())
    notify(db,row,f'Action required: {row.goods_name} — {data.action}')
    return columns(row)

@router.post('/wastage/{id}/proof')
async def proof(id:str,version:int=Form(ge=1),note:str=Form(min_length=5,max_length=3000),photos:list[UploadFile]=File(),user=Depends(current_user),db:Session=Depends(get_db)):
    images=await read_photos(photos)
    row=get_record(db,user,id,True)
    if row.submitted_by != user.id: raise HTTPException(403, 'The staff member who reported this damage must submit the evidence')
    check_version(row,version,'action_required')
    if len(note.strip()) < 5: raise HTTPException(422, 'Explain the action taken')
    # A damage photo (or previously submitted proof) cannot be reused as new proof.
    hashes=[p[2] for p in images]
    if db.scalar(select(Document.id).join(WastageEvidence,WastageEvidence.document_id==Document.id).where(Document.sha256.in_(hashes)).limit(1)):
        raise HTTPException(422, 'Use new photos of the action taken. These photos were already submitted as evidence.')
    row.status='proof_submitted'; row.version+=1
    audit(db,user,'wastage_proof_submitted','wastage',id,{'note':note.strip(),'action':row.action,'version':row.version})
    notify(db,row,f'Proof ready for review: {row.goods_name}',owners=True)
    store_photos(db,row,user,images,'proof',note.strip())
    return columns(row)

@router.post('/wastage/{id}/review')
def review(id:str,data:Review,user=Depends(boss),db:Session=Depends(get_db)):
    row=get_record(db,user,id,True); check_version(row,data.version,'proof_submitted')
    if row.submitted_by == user.id: raise HTTPException(403, 'Another Boss must review evidence you submitted')
    row.status='completed' if data.outcome=='accept' else 'action_required'; row.version+=1
    audit(db,user,'wastage_completed' if data.outcome=='accept' else 'wastage_more_proof_requested','wastage',id,data.model_dump())
    notify(db,row,f'{"Evidence accepted" if data.outcome=="accept" else "More evidence required"}: {row.goods_name}')
    return columns(row)

@router.get('/notifications')
def notifications(page_number:int=Query(1,ge=1),user=Depends(current_user),db:Session=Depends(get_db)):
    query=select(Notification).where(Notification.user_id==user.id)
    rows,total=page(db,query.order_by(Notification.created_at.desc()),page_number,25)
    unread=db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==user.id,Notification.read_at==None))
    return {'items':[columns(n) for n in rows],'total':total,'unread':unread}

@router.post('/notifications/{id}/read')
def read_notification(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    n=db.scalar(select(Notification).where(Notification.id==id,Notification.user_id==user.id))
    if not n: raise HTTPException(404,'Notification not found')
    n.read_at=n.read_at or now()
    return {'ok':True}
