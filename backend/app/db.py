from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings
import re

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, pool_pre_ping=True,
                       connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {})
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_integrity(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

if settings.database_schema and not settings.database_url.startswith('sqlite'):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',settings.database_schema):raise ValueError('Invalid database schema name')
    @event.listens_for(engine,'connect')
    def private_schema(connection,_):
        with connection.cursor() as cursor:cursor.execute('SET search_path TO '+settings.database_schema)
        connection.commit()

def get_db():
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
