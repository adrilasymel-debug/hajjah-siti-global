"""Protect audit history and enforce financial row invariants."""
from alembic import op
import sqlalchemy as sa

revision='8a20ab4d'
down_revision='2c02fbe8132c'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute("""CREATE FUNCTION forbid_audit_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Audit records are append-only'; END; $$ LANGUAGE plpgsql""")
        op.execute('CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation()')
        op.create_check_constraint('ck_bill_status','supplier_bills',"status IN ('processing','needs_review','verified','approved','rejected','processing_failed')")
        op.create_check_constraint('ck_payroll_nonnegative','payroll','basic >= 0 AND allowances >= 0 AND overtime >= 0 AND deductions >= 0')
        op.create_check_constraint('ck_item_nonnegative','invoice_line_items','quantity > 0 AND unit_price >= 0 AND tax >= 0 AND total >= 0')
    elif op.get_bind().dialect.name=='sqlite':
        op.execute("CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_logs BEGIN SELECT RAISE(ABORT, 'Audit records are append-only'); END")
        op.execute("CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_logs BEGIN SELECT RAISE(ABORT, 'Audit records are append-only'); END")

def downgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.drop_constraint('ck_item_nonnegative','invoice_line_items',type_='check')
        op.drop_constraint('ck_payroll_nonnegative','payroll',type_='check')
        op.drop_constraint('ck_bill_status','supplier_bills',type_='check')
        op.execute('DROP TRIGGER audit_append_only ON audit_logs');op.execute('DROP FUNCTION forbid_audit_mutation()')
    else:
        op.execute('DROP TRIGGER audit_no_update');op.execute('DROP TRIGGER audit_no_delete')
