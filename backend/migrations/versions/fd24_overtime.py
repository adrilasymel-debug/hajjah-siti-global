"""Add employee overtime proof and review workflow."""
from alembic import op
import sqlalchemy as sa

revision = 'fd24_overtime'
down_revision = 'fc23_bill_archive'
branch_labels = None
depends_on = None

roles=sa.table('roles',sa.column('name',sa.String()),sa.column('permissions',sa.JSON()))

def update_permissions(add):
    bind=op.get_bind()
    for name,permissions in bind.execute(sa.select(roles.c.name,roles.c.permissions)):
        permissions=list(permissions or [])
        changes=['overtime.submit_own']+(['overtime.manage'] if name=='BOSS' else [])
        if add:
            for permission in changes:
                if permission not in permissions:permissions.append(permission)
        else:
            permissions=[permission for permission in permissions if permission not in changes]
        bind.execute(roles.update().where(roles.c.name==name).values(permissions=permissions))

def upgrade():
    op.create_table('overtime_records',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('staff_name',sa.String(150),nullable=False),
        sa.Column('work_date',sa.Date(),nullable=False),
        sa.Column('start_time',sa.Time(),nullable=False),
        sa.Column('end_time',sa.Time(),nullable=False),
        sa.Column('break_minutes',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('minutes',sa.Integer(),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='submitted'),
        sa.Column('reviewed_by',sa.String(36),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('review_note',sa.Text(),nullable=False,server_default=''),
        sa.CheckConstraint('minutes > 0 AND minutes <= 720',name='ck_overtime_minutes'),
        sa.CheckConstraint('break_minutes >= 0 AND break_minutes <= 240',name='ck_overtime_break'),
        sa.CheckConstraint("status IN ('submitted','approved','rejected')",name='ck_overtime_status'),
    )
    for column in ['created_at','user_id','staff_name','work_date','status']:
        op.create_index(f'ix_overtime_records_{column}','overtime_records',[column])
    update_permissions(True)

def downgrade():
    update_permissions(False)
    op.drop_table('overtime_records')
