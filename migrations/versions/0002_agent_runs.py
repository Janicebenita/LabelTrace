"""Append-only record of LabelTrace AI queries (question, tool activity, evidence, response)."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None
def upgrade():
    # The app's startup create_all() may already have created this table (e.g. app started before
    # migrating). Treat that as already-applied instead of failing; the schema is identical.
    if 'agent_runs' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('agent_runs',sa.Column('id',sa.String(40),primary_key=True),sa.Column('key',sa.String(200),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('actor',sa.String(80),nullable=False),sa.Column('created',sa.String(50),nullable=False),
        sa.UniqueConstraint('key','version',name='uq_agent_runs_key_version'))
    op.create_index('ix_agent_runs_key','agent_runs',['key'])
def downgrade():
    op.drop_table('agent_runs')
