"""Read-only PostgreSQL + original-document backup to owner-controlled local storage."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.engine import make_url
from .config import settings
from .db import SessionLocal
from .models import Document
from .storage import storage

def backup(destination:Path):
    if not settings.database_url.startswith('postgresql+psycopg://'):
        raise RuntimeError('This backup command requires PostgreSQL. Do not use the development database for real operations.')
    executable=shutil.which('pg_dump')
    if not executable:raise RuntimeError('Install PostgreSQL client tools and add pg_dump to PATH')
    url=make_url(settings.database_url)
    folder=destination.resolve()/datetime.now(timezone.utc).strftime('hsg-%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    # Credentials are passed through the child environment, not command arguments/logs.
    env.update(PGHOST=url.host or '',PGPORT=str(url.port or 5432),PGDATABASE=url.database or '',PGUSER=url.username or '',PGPASSWORD=url.password or '',PGSSLMODE=url.query.get('sslmode','require'))
    command=[executable,'--format=custom','--no-owner','--no-acl','--file',str(folder/'database.dump')]
    if settings.database_schema:command+=['--schema',settings.database_schema]
    result=subprocess.run(command,env=env,capture_output=True,timeout=600)
    if result.returncode:raise RuntimeError('Database backup failed. Check connectivity and pg_dump version. Incomplete backup folder was retained for inspection.')
    originals=folder/'objects';originals.mkdir()
    manifest=[]
    with SessionLocal() as db:
        for doc in db.scalars(select(Document).order_by(Document.id).execution_options(yield_per=50)):
            data=storage.get(doc.key);digest=hashlib.sha256(data).hexdigest()
            if digest!=doc.sha256:raise RuntimeError('A document hash differs from its record. Backup stopped; original data was not changed.')
            (originals/doc.key).write_bytes(data)
            manifest.append({'document_id':doc.id,'key':doc.key,'sha256':digest,'bytes':len(data)})
    metadata={'company':settings.company_name,'created_at':datetime.now(timezone.utc).isoformat(),'schema':settings.database_schema or 'public','database_sha256':hashlib.sha256((folder/'database.dump').read_bytes()).hexdigest(),'documents':manifest,'complete':True}
    (folder/'manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return folder

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Back up PostgreSQL and private originals. Pause business edits first. Protect the destination because the backup contains private data.')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:print('Backup complete:',backup(args.output))
    except (RuntimeError,subprocess.TimeoutExpired) as exc:raise SystemExit(str(exc))
