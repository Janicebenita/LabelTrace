"""Frozen initial evidence schema: compatible with PostgreSQL and SQLite."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
TABLES=['users','login_sessions','products','packaging','source_documents','candidate_facts','approved_facts','label_templates','rule_sets','label_variants','change_requests','impact_assessments','label_revisions','validation_runs','review_decisions','approvals','releases','audit_events']
def upgrade():
    for name in TABLES:
        op.create_table(name,sa.Column('id',sa.String(40),primary_key=True),sa.Column('key',sa.String(200),nullable=False),
            sa.Column('version',sa.Integer(),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
            sa.Column('actor',sa.String(80),nullable=False),sa.Column('created',sa.String(50),nullable=False),
            sa.UniqueConstraint('key','version',name=f'uq_{name}_key_version'))
        op.create_index('ix_'+name+'_key',name,['key'])
    op.create_table('workflow_gate',sa.Column('id',sa.Integer(),primary_key=True))
    op.create_table('field_dependencies',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('label_id',sa.String(40),nullable=False),sa.Column('field',sa.String(80),nullable=False),
        sa.Column('fact_key',sa.String(200),nullable=False),sa.Column('condition',sa.JSON(),nullable=False),
        sa.UniqueConstraint('label_id','field'))
    op.create_index('ix_field_dependencies_label_id','field_dependencies',['label_id'])
    op.create_index('ix_field_dependencies_fact_key','field_dependencies',['fact_key'])
def downgrade():
    op.drop_table('field_dependencies');op.drop_table('workflow_gate')
    for name in reversed(TABLES):op.drop_table(name)
