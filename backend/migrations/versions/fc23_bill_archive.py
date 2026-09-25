"""Add safe invoice archiving metadata."""
from alembic import op
import sqlalchemy as sa

revision = 'fc23_bill_archive'
down_revision = 'fb22_wastage_quantity_unit'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('supplier_bills', sa.Column('archived_by', sa.String(36), nullable=True))
    op.add_column('supplier_bills', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('supplier_bills', sa.Column('archive_reason', sa.Text(), nullable=False, server_default=''))
    # Production PostgreSQL enforces the actor reference. Existing SQLite
    # development databases cannot add a foreign key without rebuilding this
    # heavily referenced table; new SQLite databases get it from metadata.
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key('fk_supplier_bills_archived_by_users', 'supplier_bills', 'users', ['archived_by'], ['id'])
    op.create_index('ix_supplier_bills_archived_at', 'supplier_bills', ['archived_at'])

def downgrade():
    op.drop_index('ix_supplier_bills_archived_at', table_name='supplier_bills')
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_supplier_bills_archived_by_users', 'supplier_bills', type_='foreignkey')
    op.drop_column('supplier_bills', 'archive_reason')
    op.drop_column('supplier_bills', 'archived_at')
    op.drop_column('supplier_bills', 'archived_by')
