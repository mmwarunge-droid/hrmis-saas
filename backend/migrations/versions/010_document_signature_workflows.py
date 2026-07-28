"""add document signature workflows

Revision ID: 010_document_signature_workflows
Revises: 009_employee_access_provisioning
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '010_document_signature_workflows'
down_revision = '009_employee_access_provisioning'
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
    op.create_table(
        'signature_requests',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'document_id',
            UUID,
            sa.ForeignKey('documents.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'created_by_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('subject', sa.String(220), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column(
            'signing_mode',
            sa.String(20),
            nullable=False,
            server_default='sequential',
        ),
        sa.Column(
            'status',
            sa.String(40),
            nullable=False,
            server_default='draft',
        ),
        sa.Column(
            'current_sequence',
            sa.Integer(),
            nullable=False,
            server_default='1',
        ),
        sa.Column(
            'due_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'sent_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'completed_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'cancelled_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column('provider', sa.String(60), nullable=True),
        sa.Column(
            'provider_request_id',
            sa.String(255),
            nullable=True,
        ),
        *timestamp_columns(),
        sa.CheckConstraint(
            "signing_mode IN ('sequential','parallel')",
            name='ck_signature_requests_signing_mode',
        ),
        sa.CheckConstraint(
            "status IN ("
            "'draft','sent','in_progress','completed',"
            "'declined','expired','cancelled'"
            ")",
            name='ck_signature_requests_status',
        ),
        sa.CheckConstraint(
            'current_sequence >= 1',
            name='ck_signature_requests_current_sequence',
        ),
    )

    op.create_index(
        'ix_signature_requests_tenant_id',
        'signature_requests',
        ['tenant_id'],
    )
    op.create_index(
        'ix_signature_requests_document_id',
        'signature_requests',
        ['document_id'],
    )
    op.create_index(
        'ix_signature_requests_created_by_id',
        'signature_requests',
        ['created_by_id'],
    )
    op.create_index(
        'ix_signature_requests_status',
        'signature_requests',
        ['status'],
    )
    op.create_index(
        'ix_signature_requests_due_at',
        'signature_requests',
        ['due_at'],
    )
    op.create_index(
        'ix_signature_requests_provider_request_id',
        'signature_requests',
        ['provider_request_id'],
    )

    op.create_table(
        'signature_recipients',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            nullable=False,
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
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'user_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'employee_id',
            UUID,
            sa.ForeignKey('employees.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('name', sa.String(240), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role_label', sa.String(120), nullable=True),
        sa.Column(
            'sequence',
            sa.Integer(),
            nullable=False,
            server_default='1',
        ),
        sa.Column(
            'status',
            sa.String(40),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'due_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'notified_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'viewed_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'signed_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'declined_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'last_reminder_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column('decline_reason', sa.Text(), nullable=True),
        sa.Column(
            'provider_recipient_id',
            sa.String(255),
            nullable=True,
        ),
        *timestamp_columns(),
        sa.CheckConstraint(
            'sequence >= 1',
            name='ck_signature_recipients_sequence',
        ),
        sa.CheckConstraint(
            "status IN ("
            "'pending','notified','viewed','signed',"
            "'declined','skipped','expired'"
            ")",
            name='ck_signature_recipients_status',
        ),
        sa.UniqueConstraint(
            'signature_request_id',
            'email',
            'sequence',
            name='uq_signature_recipient_request_email_sequence',
        ),
    )

    for name, columns in [
        (
            'ix_signature_recipients_tenant_id',
            ['tenant_id'],
        ),
        (
            'ix_signature_recipients_signature_request_id',
            ['signature_request_id'],
        ),
        (
            'ix_signature_recipients_user_id',
            ['user_id'],
        ),
        (
            'ix_signature_recipients_employee_id',
            ['employee_id'],
        ),
        (
            'ix_signature_recipients_email',
            ['email'],
        ),
        (
            'ix_signature_recipients_status',
            ['status'],
        ),
        (
            'ix_signature_recipients_due_at',
            ['due_at'],
        ),
        (
            'ix_signature_recipients_provider_recipient_id',
            ['provider_recipient_id'],
        ),
    ]:
        op.create_index(
            name,
            'signature_recipients',
            columns,
        )

    op.create_table(
        'signature_reminder_rules',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            nullable=False,
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
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'first_reminder_after_days',
            sa.Integer(),
            nullable=False,
            server_default='2',
        ),
        sa.Column(
            'reminder_interval_days',
            sa.Integer(),
            nullable=False,
            server_default='2',
        ),
        sa.Column(
            'escalation_days_before_due',
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            'next_run_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        *timestamp_columns(),
        sa.CheckConstraint(
            'first_reminder_after_days >= 0',
            name='ck_signature_reminders_first_days',
        ),
        sa.CheckConstraint(
            'reminder_interval_days >= 1',
            name='ck_signature_reminders_interval_days',
        ),
        sa.CheckConstraint(
            'escalation_days_before_due IS NULL '
            'OR escalation_days_before_due >= 0',
            name='ck_signature_reminders_escalation_days',
        ),
        sa.UniqueConstraint(
            'signature_request_id',
            name='uq_signature_reminder_request',
        ),
    )

    op.create_index(
        'ix_signature_reminder_rules_tenant_id',
        'signature_reminder_rules',
        ['tenant_id'],
    )
    op.create_index(
        'ix_signature_reminder_rules_signature_request_id',
        'signature_reminder_rules',
        ['signature_request_id'],
    )
    op.create_index(
        'ix_signature_reminder_rules_next_run_at',
        'signature_reminder_rules',
        ['next_run_at'],
    )

    op.create_table(
        'signature_events',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            nullable=False,
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
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column(
            'recipient_id',
            UUID,
            sa.ForeignKey(
                'signature_recipients.id',
                ondelete='SET NULL',
            ),
            nullable=True,
        ),
        sa.Column(
            'actor_user_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'event_type',
            sa.String(120),
            nullable=False,
        ),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            'occurred_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        *timestamp_columns(),
    )

    for name, columns in [
        ('ix_signature_events_tenant_id', ['tenant_id']),
        (
            'ix_signature_events_signature_request_id',
            ['signature_request_id'],
        ),
        (
            'ix_signature_events_recipient_id',
            ['recipient_id'],
        ),
        (
            'ix_signature_events_actor_user_id',
            ['actor_user_id'],
        ),
        ('ix_signature_events_event_type', ['event_type']),
        ('ix_signature_events_occurred_at', ['occurred_at']),
    ]:
        op.create_index(name, 'signature_events', columns)


def downgrade():
    op.drop_table('signature_events')
    op.drop_table('signature_reminder_rules')
    op.drop_table('signature_recipients')
    op.drop_table('signature_requests')
