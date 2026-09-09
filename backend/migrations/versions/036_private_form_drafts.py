"""Private resumable form drafts, separate from executable workflows."""
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

revision = '036_private_form_drafts'
down_revision = '035_hr_native_execution'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('form_drafts',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('owner_id', GUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('scope_key', sa.String(36), nullable=False),
        sa.Column('workflow_key', sa.String(200), nullable=False),
        sa.Column('title', sa.String(220), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('owner_id', 'scope_key', 'workflow_key', name='uq_form_draft_owner_scope_key'),
    )
    op.create_index('ix_form_drafts_owner_id', 'form_drafts', ['owner_id'])
    op.create_index('ix_form_drafts_tenant_id', 'form_drafts', ['tenant_id'])


def downgrade():
    op.drop_table('form_drafts')
