"""Wastage evidence, owner instructions and private notifications."""
from alembic import op
import sqlalchemy as sa

revision = 'f920_wastage'
down_revision = 'e810_unit'
branch_labels = None
depends_on = None

def record():
    return [sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)]

def upgrade():
    op.create_table('wastage', *record(),
        sa.Column('goods_name', sa.String(200), nullable=False),
        sa.Column('damage_date', sa.Date(), nullable=False),
        sa.Column('quantity_kg', sa.Numeric(16,3), nullable=False),
        sa.Column('damage', sa.Text(), nullable=False),
        sa.Column('submitted_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('staff_name', sa.String(150), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('decided_at', sa.DateTime(timezone=True)),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.CheckConstraint('quantity_kg > 0'))
    op.create_table('wastage_evidence', *record(),
        sa.Column('wastage_id', sa.String(36), sa.ForeignKey('wastage.id'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=False, unique=True),
        sa.Column('phase', sa.String(20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False))
    op.create_table('notifications', *record(),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(250), nullable=False),
        sa.Column('wastage_id', sa.String(36), sa.ForeignKey('wastage.id'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)))
    for table, cols in {'wastage':['created_at','goods_name','damage_date','submitted_by','status'], 'wastage_evidence':['created_at','wastage_id'], 'notifications':['created_at','user_id','wastage_id']}.items():
        for col in cols: op.create_index('ix_'+table+'_'+col, table, [col])

def downgrade():
    op.drop_table('notifications')
    op.drop_table('wastage_evidence')
    op.drop_table('wastage')
