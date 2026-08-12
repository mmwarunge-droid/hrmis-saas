"""add signature discussions and signed-name evidence

Revision ID: 021_workflow_hardening
Revises: 020_secure_account_invitations
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

UUID = postgresql.UUID(as_uuid=True)

revision = '021_workflow_hardening'
down_revision = '020_secure_account_invitations'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_employees_status', 'employees', type_='check')
    op.create_check_constraint(
        'ck_employees_status',
        'employees',
        "employment_status IN ('active','probation','inactive','suspended','terminated')",
    )
    op.add_column('signature_recipients', sa.Column('signature_name', sa.String(length=240), nullable=True))
    op.create_table(
        'signature_discussions',
        sa.Column('id', UUID, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, nullable=False),
        sa.Column('signature_request_id', UUID, nullable=False),
        sa.Column('recipient_id', UUID, nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_user_id', UUID, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("status IN ('open','resolved')", name='ck_signature_discussions_status'),
        sa.ForeignKeyConstraint(['recipient_id'], ['signature_recipients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['signature_request_id'], ['signature_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signature_request_id', 'recipient_id', name='uq_signature_discussion_request_recipient'),
    )
    op.create_index('ix_signature_discussions_signature_request_id', 'signature_discussions', ['signature_request_id'])
    op.create_index('ix_signature_discussions_recipient_id', 'signature_discussions', ['recipient_id'])
    op.create_index('ix_signature_discussions_status', 'signature_discussions', ['status'])
    op.create_table(
        'signature_discussion_comments',
        sa.Column('id', UUID, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, nullable=False),
        sa.Column('discussion_id', UUID, nullable=False),
        sa.Column('author_user_id', UUID, nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('mentioned_user_ids_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['discussion_id'], ['signature_discussions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_signature_discussion_comments_discussion_id', 'signature_discussion_comments', ['discussion_id'])
    op.create_index('ix_signature_discussion_comments_author_user_id', 'signature_discussion_comments', ['author_user_id'])


def downgrade():
    op.execute(sa.text("UPDATE employees SET employment_status = 'suspended' WHERE employment_status = 'inactive'"))
    op.drop_constraint('ck_employees_status', 'employees', type_='check')
    op.create_check_constraint(
        'ck_employees_status',
        'employees',
        "employment_status IN ('active','probation','suspended','terminated')",
    )
    op.drop_index('ix_signature_discussion_comments_author_user_id', table_name='signature_discussion_comments')
    op.drop_index('ix_signature_discussion_comments_discussion_id', table_name='signature_discussion_comments')
    op.drop_table('signature_discussion_comments')
    op.drop_index('ix_signature_discussions_status', table_name='signature_discussions')
    op.drop_index('ix_signature_discussions_recipient_id', table_name='signature_discussions')
    op.drop_index('ix_signature_discussions_signature_request_id', table_name='signature_discussions')
    op.drop_table('signature_discussions')
    op.drop_column('signature_recipients', 'signature_name')
