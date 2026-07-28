"""ingest and verify qualified signature evidence

Revision ID: 013_qes_evidence_ingestion
Revises: 012_qes_provider_workflow
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa


revision = '013_qes_evidence_ingestion'
down_revision = '012_qes_provider_workflow'
branch_labels = None
depends_on = None


EVIDENCE_STATUS_CHECK = (
    "evidence_status IN ("
    "'not_required','awaiting_provider','pending',"
    "'processing','retry_scheduled','verified','failed'"
    ")"
)


def upgrade():
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_status',
            sa.String(length=30),
            nullable=False,
            server_default='not_required',
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_attempts',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_next_attempt_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_last_attempt_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_locked_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_last_error',
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_verification_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    op.execute(sa.text(
        """
        UPDATE signature_requests
        SET evidence_status = CASE
            WHEN provider = 'dropbox_sign'
                 AND assurance_level = 'qes'
                 AND evidence_completed_at IS NOT NULL
                THEN 'verified'
            WHEN provider = 'dropbox_sign'
                 AND assurance_level = 'qes'
                 AND provider_downloadable_at IS NOT NULL
                THEN 'pending'
            WHEN provider = 'dropbox_sign'
                 AND assurance_level = 'qes'
                THEN 'awaiting_provider'
            ELSE 'not_required'
        END,
        evidence_next_attempt_at = CASE
            WHEN provider = 'dropbox_sign'
                 AND assurance_level = 'qes'
                 AND provider_downloadable_at IS NOT NULL
                 AND evidence_completed_at IS NULL
                THEN CURRENT_TIMESTAMP
            ELSE NULL
        END
        """
    ))

    op.create_check_constraint(
        'ck_signature_requests_evidence_status',
        'signature_requests',
        EVIDENCE_STATUS_CHECK,
    )
    op.create_check_constraint(
        'ck_signature_requests_evidence_attempts',
        'signature_requests',
        'evidence_attempts >= 0',
    )
    op.create_index(
        'ix_signature_requests_evidence_status',
        'signature_requests',
        ['evidence_status'],
        unique=False,
    )
    op.create_index(
        'ix_signature_requests_evidence_next_attempt_at',
        'signature_requests',
        ['evidence_next_attempt_at'],
        unique=False,
    )
    op.create_index(
        'ix_signature_requests_evidence_locked_at',
        'signature_requests',
        ['evidence_locked_at'],
        unique=False,
    )
    op.create_index(
        'ix_signature_requests_evidence_queue',
        'signature_requests',
        ['evidence_status', 'evidence_next_attempt_at'],
        unique=False,
    )


def downgrade():
    op.drop_index(
        'ix_signature_requests_evidence_queue',
        table_name='signature_requests',
    )
    op.drop_index(
        'ix_signature_requests_evidence_locked_at',
        table_name='signature_requests',
    )
    op.drop_index(
        'ix_signature_requests_evidence_next_attempt_at',
        table_name='signature_requests',
    )
    op.drop_index(
        'ix_signature_requests_evidence_status',
        table_name='signature_requests',
    )
    op.drop_constraint(
        'ck_signature_requests_evidence_attempts',
        'signature_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_signature_requests_evidence_status',
        'signature_requests',
        type_='check',
    )
    op.drop_column(
        'signature_requests',
        'evidence_verification_json',
    )
    op.drop_column(
        'signature_requests',
        'evidence_last_error',
    )
    op.drop_column(
        'signature_requests',
        'evidence_locked_at',
    )
    op.drop_column(
        'signature_requests',
        'evidence_last_attempt_at',
    )
    op.drop_column(
        'signature_requests',
        'evidence_next_attempt_at',
    )
    op.drop_column(
        'signature_requests',
        'evidence_attempts',
    )
    op.drop_column(
        'signature_requests',
        'evidence_status',
    )
