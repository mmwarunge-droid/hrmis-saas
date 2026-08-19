# signature discussion collaboration and immutable comment history
#
# Revision ID: 024_signature_discussion
# Revises: 023_native_pdf_signing
# Create Date: 2026-08-19

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '024_signature_discussion'
down_revision = '023_native_pdf_signing'
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'signature_discussion_comments',
        sa.Column(
            'edited_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_discussion_comments',
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_discussion_comments',
        sa.Column(
            'deleted_by_user_id',
            UUID,
            nullable=True,
        ),
    )
    op.create_foreign_key(
        'fk_signature_discussion_comments_deleted_by_user',
        'signature_discussion_comments',
        'users',
        ['deleted_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_signature_discussion_comments_deleted_at',
        'signature_discussion_comments',
        ['deleted_at'],
    )

    op.create_table(
        'signature_discussion_participants',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey(
                'tenants.id',
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'discussion_id',
            UUID,
            sa.ForeignKey(
                'signature_discussions.id',
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'user_id',
            UUID,
            sa.ForeignKey(
                'users.id',
                ondelete='SET NULL',
            ),
            nullable=True,
        ),
        sa.Column(
            'added_by_user_id',
            UUID,
            sa.ForeignKey(
                'users.id',
                ondelete='SET NULL',
            ),
            nullable=True,
        ),
        sa.Column(
            'source',
            sa.String(30),
            nullable=False,
            server_default='mention',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.CheckConstraint(
            "source IN ('mention','manual')",
            name='ck_signature_discussion_participants_source',
        ),
        sa.UniqueConstraint(
            'discussion_id',
            'user_id',
            name='uq_signature_discussion_participant_user',
        ),
    )
    op.create_index(
        'ix_signature_discussion_participants_tenant_id',
        'signature_discussion_participants',
        ['tenant_id'],
    )
    op.create_index(
        'ix_signature_discussion_participants_discussion_id',
        'signature_discussion_participants',
        ['discussion_id'],
    )
    op.create_index(
        'ix_signature_discussion_participants_user_id',
        'signature_discussion_participants',
        ['user_id'],
    )

    op.create_table(
        'signature_discussion_comment_revisions',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey(
                'tenants.id',
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'comment_id',
            UUID,
            sa.ForeignKey(
                'signature_discussion_comments.id',
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'actor_user_id',
            UUID,
            sa.ForeignKey(
                'users.id',
                ondelete='SET NULL',
            ),
            nullable=True,
        ),
        sa.Column(
            'revision_type',
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            'body',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'mentioned_user_ids_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            'occurred_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.CheckConstraint(
            "revision_type IN ('created','edited','deleted')",
            name='ck_signature_discussion_revision_type',
        ),
    )
    op.create_index(
        'ix_signature_discussion_comment_revisions_tenant_id',
        'signature_discussion_comment_revisions',
        ['tenant_id'],
    )
    op.create_index(
        'ix_signature_discussion_comment_revisions_comment_id',
        'signature_discussion_comment_revisions',
        ['comment_id'],
    )
    op.create_index(
        'ix_signature_discussion_comment_revisions_actor_user_id',
        'signature_discussion_comment_revisions',
        ['actor_user_id'],
    )
    op.create_index(
        'ix_signature_discussion_comment_revisions_occurred_at',
        'signature_discussion_comment_revisions',
        ['occurred_at'],
    )


def downgrade():
    op.drop_index(
        'ix_signature_discussion_comment_revisions_occurred_at',
        table_name='signature_discussion_comment_revisions',
    )
    op.drop_index(
        'ix_signature_discussion_comment_revisions_actor_user_id',
        table_name='signature_discussion_comment_revisions',
    )
    op.drop_index(
        'ix_signature_discussion_comment_revisions_comment_id',
        table_name='signature_discussion_comment_revisions',
    )
    op.drop_index(
        'ix_signature_discussion_comment_revisions_tenant_id',
        table_name='signature_discussion_comment_revisions',
    )
    op.drop_table('signature_discussion_comment_revisions')

    op.drop_index(
        'ix_signature_discussion_participants_user_id',
        table_name='signature_discussion_participants',
    )
    op.drop_index(
        'ix_signature_discussion_participants_discussion_id',
        table_name='signature_discussion_participants',
    )
    op.drop_index(
        'ix_signature_discussion_participants_tenant_id',
        table_name='signature_discussion_participants',
    )
    op.drop_table('signature_discussion_participants')

    op.drop_index(
        'ix_signature_discussion_comments_deleted_at',
        table_name='signature_discussion_comments',
    )
    op.drop_constraint(
        'fk_signature_discussion_comments_deleted_by_user',
        'signature_discussion_comments',
        type_='foreignkey',
    )
    op.drop_column(
        'signature_discussion_comments',
        'deleted_by_user_id',
    )
    op.drop_column(
        'signature_discussion_comments',
        'deleted_at',
    )
    op.drop_column(
        'signature_discussion_comments',
        'edited_at',
    )
