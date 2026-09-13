from alembic import context
from app.db import Base, engine
from app import models
from app.config import settings
from sqlalchemy import text

if context.is_offline_mode():
    context.configure(url=str(engine.url),target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    if settings.database_schema and engine.dialect.name=='postgresql':
        with engine.begin() as setup:setup.execute(text('CREATE SCHEMA IF NOT EXISTS '+settings.database_schema))
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=engine.dialect.name=='sqlite')
        with context.begin_transaction():context.run_migrations()
