"""Preserve invoice units for weight-based dried seafood purchasing."""
from alembic import op
import sqlalchemy as sa
revision='e810_unit'
down_revision='c9275c57a8d5'
branch_labels=None
depends_on=None
def upgrade():op.add_column('invoice_line_items',sa.Column('unit',sa.String(20),nullable=False,server_default='unit'))
def downgrade():
    with op.batch_alter_table('invoice_line_items') as batch:batch.drop_column('unit')
