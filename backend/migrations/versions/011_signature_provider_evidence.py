# add signature provider evidence
#
# Revision ID: 011_signature_provider_evidence
# Revises: 010_document_signature_workflows
# Create Date: 2026-07-28

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '011_signature_provider_evidence'
down_revision = '010_document_signature_workflows'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def timestamp_columns():
    return [
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
    ]


def upgrade():
    op.add_column(
        'signature_requests',
        sa.Column('provider_status', sa.String(80)),
    )
    op.add_column(
        'signature_requests',
        sa.Column('provider_test_mode', sa.Boolean()),
    )
    op.add_column(
        'signature_requests',
        sa.Column('assurance_level', sa.String(30)),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'provider_metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'provider_created_at',
            sa.DateTime(timezone=True),
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'provider_downloadable_at',
            sa.DateTime(timezone=True),
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'evidence_completed_at',
            sa.DateTime(timezone=True),
        ),
    )
    op.create_check_constraint(
        'ck_signature_requests_assurance_level',
        'signature_requests',
        (
            "assurance_level IS NULL OR "
            "assurance_level IN ('standard','aes','qes')"
        ),
    )
    op.create_index(
        'ix_signature_requests_provider_status',
        'signature_requests',
        ['provider_status'],
    )

    op.add_column(
        'signature_recipients',
        sa.Column('provider_status', sa.String(80)),
    )
    op.add_column(
        'signature_recipients',
        sa.Column(
            'provider_metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_index(
        'ix_signature_recipients_provider_status',
        'signature_recipients',
        ['provider_status'],
    )

    op.create_table(
        'signature_artifacts',
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
            sa.ForeignKey(
                'signature_requests.id',
                ondelete='RESTRICT',
            ),
            nullable=False,
        ),
        sa.Column('artifact_type', sa.String(40), nullable=False),
        sa.Column('provider', sa.String(60), nullable=False),
        sa.Column('provider_artifact_id', sa.String(255)),
        sa.Column(
            'original_filename',
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            'stored_filename',
            sa.String(255),
            nullable=False,
            unique=True,
        ),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(120)),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column(
            'checksum_sha256',
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            'captured_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        *timestamp_columns(),
        sa.CheckConstraint(
            "artifact_type IN ("
            "'original_document','signed_document',"
            "'audit_trail','completion_certificate'"
            ")",
            name='ck_signature_artifacts_type',
        ),
        sa.CheckConstraint(
            'size_bytes >= 0',
            name='ck_signature_artifacts_size',
        ),
        sa.UniqueConstraint(
            'signature_request_id',
            'artifact_type',
            name='uq_signature_artifact_request_type',
        ),
    )

    for name, columns in [
        ('ix_signature_artifacts_tenant_id', ['tenant_id']),
        (
            'ix_signature_artifacts_signature_request_id',
            ['signature_request_id'],
        ),
        (
            'ix_signature_artifacts_artifact_type',
            ['artifact_type'],
        ),
        ('ix_signature_artifacts_provider', ['provider']),
        (
            'ix_signature_artifacts_provider_artifact_id',
            ['provider_artifact_id'],
        ),
        (
            'ix_signature_artifacts_checksum_sha256',
            ['checksum_sha256'],
        ),
        (
            'ix_signature_artifacts_captured_at',
            ['captured_at'],
        ),
    ]:
        op.create_index(
            name,
            'signature_artifacts',
            columns,
        )

    op.create_table(
        'signature_provider_events',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey('tenants.id', ondelete='SET NULL'),
        ),
        sa.Column(
            'signature_request_id',
            UUID,
            sa.ForeignKey(
                'signature_requests.id',
                ondelete='SET NULL',
            ),
        ),
        sa.Column('provider', sa.String(60), nullable=False),
        sa.Column(
            'provider_event_id',
            sa.String(128),
            nullable=False,
        ),
        sa.Column('provider_request_id', sa.String(255)),
        sa.Column('event_type', sa.String(120), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True)),
        sa.Column(
            'payload_sha256',
            sa.String(64),
            nullable=False,
        ),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column(
            'signature_valid',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            'processing_status',
            sa.String(30),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'processing_attempts',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'received_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('last_error', sa.Text()),
        *timestamp_columns(),
        sa.CheckConstraint(
            "processing_status IN ("
            "'pending','processed','ignored',"
            "'failed','unmatched'"
            ")",
            name='ck_signature_provider_events_status',
        ),
        sa.CheckConstraint(
            'processing_attempts >= 0',
            name='ck_signature_provider_events_attempts',
        ),
        sa.UniqueConstraint(
            'provider',
            'provider_event_id',
            name='uq_signature_provider_event',
        ),
    )

    for name, columns in [
        (
            'ix_signature_provider_events_tenant_id',
            ['tenant_id'],
        ),
        (
            'ix_signature_provider_events_signature_request_id',
            ['signature_request_id'],
        ),
        (
            'ix_signature_provider_events_provider',
            ['provider'],
        ),
        (
            'ix_signature_provider_events_provider_request_id',
            ['provider_request_id'],
        ),
        (
            'ix_signature_provider_events_event_type',
            ['event_type'],
        ),
        (
            'ix_signature_provider_events_event_time',
            ['event_time'],
        ),
        (
            'ix_signature_provider_events_payload_sha256',
            ['payload_sha256'],
        ),
        (
            'ix_signature_provider_events_processing_status',
            ['processing_status'],
        ),
        (
            'ix_signature_provider_events_received_at',
            ['received_at'],
        ),
    ]:
        op.create_index(
            name,
            'signature_provider_events',
            columns,
        )


def downgrade():
    op.drop_table('signature_provider_events')
    op.drop_table('signature_artifacts')

    op.drop_index(
        'ix_signature_recipients_provider_status',
        table_name='signature_recipients',
    )
    op.drop_column(
        'signature_recipients',
        'provider_metadata_json',
    )
    op.drop_column(
        'signature_recipients',
        'provider_status',
    )

    op.drop_index(
        'ix_signature_requests_provider_status',
        table_name='signature_requests',
    )
    op.drop_constraint(
        'ck_signature_requests_assurance_level',
        'signature_requests',
        type_='check',
    )
    for column in (
        'evidence_completed_at',
        'provider_downloadable_at',
        'provider_created_at',
        'provider_metadata_json',
        'assurance_level',
        'provider_test_mode',
        'provider_status',
    ):
        op.drop_column('signature_requests', column)
