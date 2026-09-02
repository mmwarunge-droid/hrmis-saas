"""link replacement signature requests to their original request.

Revision ID: 030_signature_resends
Revises: 029_training_attempts
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '030_signature_resends'
down_revision = '029_training_attempts'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'signature_requests',
        sa.Column(
            'resend_of_request_id',
            UUID,
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'resend_attempt',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.create_foreign_key(
        'fk_signature_requests_resend_of_request_id',
        'signature_requests',
        'signature_requests',
        ['resend_of_request_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_signature_requests_resend_of_request_id',
        'signature_requests',
        ['resend_of_request_id'],
        unique=False,
    )
    op.create_check_constraint(
        'ck_signature_requests_resend_attempt',
        'signature_requests',
        'resend_attempt >= 0',
    )
    op.alter_column(
        'signature_requests',
        'resend_attempt',
        server_default=None,
    )


def downgrade():
    op.drop_constraint(
        'ck_signature_requests_resend_attempt',
        'signature_requests',
        type_='check',
    )
    op.drop_index(
        'ix_signature_requests_resend_of_request_id',
        table_name='signature_requests',
    )
    op.drop_constraint(
        'fk_signature_requests_resend_of_request_id',
        'signature_requests',
        type_='foreignkey',
    )
    op.drop_column('signature_requests', 'resend_attempt')
    op.drop_column('signature_requests', 'resend_of_request_id')
