"""enforce qualified signature workflow invariants

Revision ID: 012_qes_provider_workflow
Revises: 011_signature_provider_evidence
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa


revision = '012_qes_provider_workflow'
down_revision = '011_signature_provider_evidence'
branch_labels = None
depends_on = None


ACTIVE_REQUEST_PREDICATE = (
    "status IN ('draft','sent','in_progress')"
)


def upgrade():
    bind = op.get_bind()
    duplicate = bind.execute(sa.text(
        """
        SELECT document_id
        FROM signature_requests
        WHERE status IN ('draft','sent','in_progress')
        GROUP BY document_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )).first()

    if duplicate:
        raise RuntimeError(
            'Cannot enforce one active signature request per '
            'document while duplicate active requests exist.'
        )

    op.drop_constraint(
        'ck_signature_requests_status',
        'signature_requests',
        type_='check',
    )
    op.create_check_constraint(
        'ck_signature_requests_status',
        'signature_requests',
        (
            "status IN ("
            "'draft','sent','in_progress','completed',"
            "'declined','expired','cancelled','failed'"
            ")"
        ),
    )
    op.create_index(
        'uq_signature_requests_active_document',
        'signature_requests',
        ['document_id'],
        unique=True,
        postgresql_where=sa.text(ACTIVE_REQUEST_PREDICATE),
        sqlite_where=sa.text(ACTIVE_REQUEST_PREDICATE),
    )


def downgrade():
    op.drop_index(
        'uq_signature_requests_active_document',
        table_name='signature_requests',
    )
    op.drop_constraint(
        'ck_signature_requests_status',
        'signature_requests',
        type_='check',
    )
    op.create_check_constraint(
        'ck_signature_requests_status',
        'signature_requests',
        (
            "status IN ("
            "'draft','sent','in_progress','completed',"
            "'declined','expired','cancelled'"
            ")"
        ),
    )
