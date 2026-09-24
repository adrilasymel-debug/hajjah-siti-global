"""Allow wastage to be measured by weight or by whole units."""
from alembic import op
import sqlalchemy as sa

revision = 'fb22_wastage_quantity_unit'
down_revision = 'fa21_email'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('wastage', 'quantity_kg', new_column_name='quantity',
                    existing_type=sa.Numeric(16, 3), existing_nullable=False)
    op.add_column('wastage', sa.Column('quantity_unit', sa.String(10), nullable=False, server_default='kg'))
    # SQLite cannot add CHECK constraints without rebuilding the table, which
    # is referenced by evidence and notifications. The API validates there.
    if op.get_bind().dialect.name != 'sqlite':
        op.create_check_constraint('ck_wastage_quantity_unit', 'wastage',
                                   "quantity_unit IN ('kg', 'unit')")
        op.create_check_constraint('ck_wastage_whole_units', 'wastage',
                                   "quantity_unit = 'kg' OR quantity = CAST(quantity AS INTEGER)")

def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM wastage WHERE quantity_unit = 'unit'")).scalar():
        raise RuntimeError('Cannot downgrade wastage with unit-based reports')
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('ck_wastage_whole_units', 'wastage', type_='check')
        op.drop_constraint('ck_wastage_quantity_unit', 'wastage', type_='check')
    op.drop_column('wastage', 'quantity_unit')
    op.alter_column('wastage', 'quantity', new_column_name='quantity_kg',
                    existing_type=sa.Numeric(16, 3), existing_nullable=False)
