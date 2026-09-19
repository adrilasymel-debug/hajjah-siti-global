"""Durable transactional email outbox."""
from alembic import op
import sqlalchemy as sa
revision='fa21_email'
down_revision='f920_wastage'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('email_deliveries',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('event_id',sa.String(36),sa.ForeignKey('audit_logs.id'),nullable=False),
        sa.Column('subject',sa.String(150),nullable=False),
        sa.Column('path',sa.String(100),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('available_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_error',sa.String(200),nullable=False),
        sa.Column('sent_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('event_id','user_id'))
    for col in ['created_at','user_id','status','available_at']:
        op.create_index('ix_email_deliveries_'+col,'email_deliveries',[col])

def downgrade():op.drop_table('email_deliveries')
