# native PDF signing fields and consent evidence
#
# Revision ID: 023_native_pdf_signing
# Revises: 022_security_workflow_boundaries
# Create Date: 2026-08-17

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '023_native_pdf_signing'
down_revision = '022_security_workflow_boundaries'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'signature_recipients',
        sa.Column('signature_method', sa.String(40)),
    )
    op.add_column(
        'signature_recipients',
        sa.Column('signature_style', sa.String(40)),
    )
    op.add_column(
        'signature_recipients',
        sa.Column('consented_at', sa.DateTime(timezone=True)),
    )
    op.add_column(
        'signature_recipients',
        sa.Column('consent_version', sa.String(40)),
    )

    op.create_table(
        'signature_fields',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'signature_request_id',
            UUID,
            sa.ForeignKey('signature_requests.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'recipient_id',
            UUID,
            sa.ForeignKey('signature_recipients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('field_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(160)),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('width', sa.Float(), nullable=False),
        sa.Column('height', sa.Float(), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('value', sa.Text()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
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
            "field_type IN ('signature','date')",
            name='ck_signature_fields_type',
        ),
        sa.CheckConstraint(
            'page_number >= 1',
            name='ck_signature_fields_page_number',
        ),
        sa.CheckConstraint(
            'x >= 0 AND x <= 1 AND y >= 0 AND y <= 1',
            name='ck_signature_fields_origin',
        ),
        sa.CheckConstraint(
            'width > 0 AND width <= 1 AND height > 0 AND height <= 1',
            name='ck_signature_fields_dimensions',
        ),
        sa.CheckConstraint(
            'x + width <= 1 AND y + height <= 1',
            name='ck_signature_fields_page_bounds',
        ),
    )
    op.create_index('ix_signature_fields_tenant_id', 'signature_fields', ['tenant_id'])
    op.create_index(
        'ix_signature_fields_signature_request_id',
        'signature_fields',
        ['signature_request_id'],
    )
    op.create_index(
        'ix_signature_fields_recipient_id',
        'signature_fields',
        ['recipient_id'],
    )
    op.create_index(
        'ix_signature_fields_field_type',
        'signature_fields',
        ['field_type'],
    )


def downgrade():
    op.drop_index('ix_signature_fields_field_type', table_name='signature_fields')
    op.drop_index('ix_signature_fields_recipient_id', table_name='signature_fields')
    op.drop_index(
        'ix_signature_fields_signature_request_id',
        table_name='signature_fields',
    )
    op.drop_index('ix_signature_fields_tenant_id', table_name='signature_fields')
    op.drop_table('signature_fields')
    op.drop_column('signature_recipients', 'consent_version')
    op.drop_column('signature_recipients', 'consented_at')
    op.drop_column('signature_recipients', 'signature_style')
    op.drop_column('signature_recipients', 'signature_method')
