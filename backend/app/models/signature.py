from app.extensions import db
from app.models.base import (
    GUID,
    ReprMixin,
    TenantMixin,
    TimestampMixin,
    utcnow,
    uuid_pk,
)


class SignatureRequest(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_requests'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    document_id = db.Column(
        GUID(),
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    created_by_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    subject = db.Column(db.String(220), nullable=False)
    message = db.Column(db.Text)
    signing_mode = db.Column(
        db.String(20),
        nullable=False,
        default='sequential',
    )
    status = db.Column(
        db.String(40),
        nullable=False,
        default='draft',
        index=True,
    )
    current_sequence = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    due_at = db.Column(db.DateTime, nullable=True, index=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    provider = db.Column(db.String(60), nullable=True)
    provider_request_id = db.Column(
        db.String(255),
        nullable=True,
        index=True,
    )
    provider_status = db.Column(
        db.String(80),
        nullable=True,
        index=True,
    )
    provider_test_mode = db.Column(
        db.Boolean,
        nullable=True,
    )
    assurance_level = db.Column(
        db.String(30),
        nullable=True,
    )
    provider_metadata_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )
    provider_created_at = db.Column(
        db.DateTime,
        nullable=True,
    )
    provider_downloadable_at = db.Column(
        db.DateTime,
        nullable=True,
    )
    evidence_completed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    document = db.relationship('Document')
    created_by = db.relationship(
        'User',
        foreign_keys=[created_by_id],
    )
    recipients = db.relationship(
        'SignatureRecipient',
        back_populates='signature_request',
        cascade='all, delete-orphan',
        order_by='SignatureRecipient.sequence',
    )
    events = db.relationship(
        'SignatureEvent',
        back_populates='signature_request',
        cascade='all, delete-orphan',
        order_by='SignatureEvent.created_at',
    )
    reminder_rule = db.relationship(
        'SignatureReminderRule',
        back_populates='signature_request',
        cascade='all, delete-orphan',
        uselist=False,
    )
    artifacts = db.relationship(
        'SignatureArtifact',
        back_populates='signature_request',
        passive_deletes=True,
        order_by='SignatureArtifact.captured_at',
    )
    provider_events = db.relationship(
        'SignatureProviderEvent',
        back_populates='signature_request',
        passive_deletes=True,
        order_by='SignatureProviderEvent.received_at',
    )

    __table_args__ = (
        db.CheckConstraint(
            "signing_mode IN ('sequential','parallel')",
            name='ck_signature_requests_signing_mode',
        ),
        db.CheckConstraint(
            "status IN ("
            "'draft','sent','in_progress','completed',"
            "'declined','expired','cancelled','failed'"
            ")",
            name='ck_signature_requests_status',
        ),
        db.CheckConstraint(
            'current_sequence >= 1',
            name='ck_signature_requests_current_sequence',
        ),
        db.CheckConstraint(
            "assurance_level IS NULL OR "
            "assurance_level IN ('standard','aes','qes')",
            name='ck_signature_requests_assurance_level',
        ),
        db.Index(
            'uq_signature_requests_active_document',
            'document_id',
            unique=True,
            postgresql_where=db.text(
                "status IN ('draft','sent','in_progress')",
            ),
            sqlite_where=db.text(
                "status IN ('draft','sent','in_progress')",
            ),
        ),
    )

    @property
    def signed_count(self):
        return sum(
            recipient.status == 'signed'
            for recipient in self.recipients
        )

    @property
    def recipient_count(self):
        return len(self.recipients)

    def to_dict(self, include_recipients=True):
        data = {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'document_id': str(self.document_id),
            'created_by_id': (
                str(self.created_by_id)
                if self.created_by_id
                else None
            ),
            'subject': self.subject,
            'message': self.message,
            'signing_mode': self.signing_mode,
            'status': self.status,
            'current_sequence': self.current_sequence,
            'recipient_count': self.recipient_count,
            'signed_count': self.signed_count,
            'due_at': (
                self.due_at.isoformat()
                if self.due_at
                else None
            ),
            'sent_at': (
                self.sent_at.isoformat()
                if self.sent_at
                else None
            ),
            'completed_at': (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            'cancelled_at': (
                self.cancelled_at.isoformat()
                if self.cancelled_at
                else None
            ),
            'provider': self.provider,
            'provider_request_id': self.provider_request_id,
            'provider_status': self.provider_status,
            'provider_test_mode': self.provider_test_mode,
            'assurance_level': self.assurance_level,
            'provider_metadata_json': (
                self.provider_metadata_json
            ),
            'provider_created_at': (
                self.provider_created_at.isoformat()
                if self.provider_created_at
                else None
            ),
            'provider_downloadable_at': (
                self.provider_downloadable_at.isoformat()
                if self.provider_downloadable_at
                else None
            ),
            'evidence_completed_at': (
                self.evidence_completed_at.isoformat()
                if self.evidence_completed_at
                else None
            ),
            'artifact_count': len(self.artifacts),
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            'updated_at': (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }

        if include_recipients:
            data['recipients'] = [
                recipient.to_dict()
                for recipient in self.recipients
            ]

        return data


class SignatureRecipient(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_recipients'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    name = db.Column(db.String(240), nullable=False)
    email = db.Column(
        db.String(255),
        nullable=False,
        index=True,
    )
    role_label = db.Column(db.String(120), nullable=True)
    sequence = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )
    status = db.Column(
        db.String(40),
        nullable=False,
        default='pending',
        index=True,
    )

    due_at = db.Column(db.DateTime, nullable=True, index=True)
    notified_at = db.Column(db.DateTime, nullable=True)
    viewed_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)
    declined_at = db.Column(db.DateTime, nullable=True)
    last_reminder_at = db.Column(db.DateTime, nullable=True)

    decline_reason = db.Column(db.Text, nullable=True)
    provider_recipient_id = db.Column(
        db.String(255),
        nullable=True,
        index=True,
    )
    provider_status = db.Column(
        db.String(80),
        nullable=True,
        index=True,
    )
    provider_metadata_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='recipients',
    )
    user = db.relationship('User', foreign_keys=[user_id])
    employee = db.relationship(
        'Employee',
        foreign_keys=[employee_id],
    )
    events = db.relationship(
        'SignatureEvent',
        back_populates='recipient',
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            'sequence >= 1',
            name='ck_signature_recipients_sequence',
        ),
        db.CheckConstraint(
            "status IN ("
            "'pending','notified','viewed','signed',"
            "'declined','skipped','expired'"
            ")",
            name='ck_signature_recipients_status',
        ),
        db.UniqueConstraint(
            'signature_request_id',
            'email',
            'sequence',
            name='uq_signature_recipient_request_email_sequence',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(
                self.signature_request_id,
            ),
            'user_id': (
                str(self.user_id)
                if self.user_id
                else None
            ),
            'employee_id': (
                str(self.employee_id)
                if self.employee_id
                else None
            ),
            'name': self.name,
            'email': self.email,
            'role_label': self.role_label,
            'sequence': self.sequence,
            'status': self.status,
            'due_at': (
                self.due_at.isoformat()
                if self.due_at
                else None
            ),
            'notified_at': (
                self.notified_at.isoformat()
                if self.notified_at
                else None
            ),
            'viewed_at': (
                self.viewed_at.isoformat()
                if self.viewed_at
                else None
            ),
            'signed_at': (
                self.signed_at.isoformat()
                if self.signed_at
                else None
            ),
            'declined_at': (
                self.declined_at.isoformat()
                if self.declined_at
                else None
            ),
            'last_reminder_at': (
                self.last_reminder_at.isoformat()
                if self.last_reminder_at
                else None
            ),
            'decline_reason': self.decline_reason,
            'provider_recipient_id': (
                self.provider_recipient_id
            ),
            'provider_status': self.provider_status,
            'provider_metadata_json': (
                self.provider_metadata_json
            ),
        }


class SignatureReminderRule(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_reminder_rules'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    first_reminder_after_days = db.Column(
        db.Integer,
        nullable=False,
        default=2,
    )
    reminder_interval_days = db.Column(
        db.Integer,
        nullable=False,
        default=2,
    )
    escalation_days_before_due = db.Column(
        db.Integer,
        nullable=True,
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    next_run_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='reminder_rule',
    )

    __table_args__ = (
        db.CheckConstraint(
            'first_reminder_after_days >= 0',
            name='ck_signature_reminders_first_days',
        ),
        db.CheckConstraint(
            'reminder_interval_days >= 1',
            name='ck_signature_reminders_interval_days',
        ),
        db.CheckConstraint(
            'escalation_days_before_due IS NULL '
            'OR escalation_days_before_due >= 0',
            name='ck_signature_reminders_escalation_days',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(
                self.signature_request_id,
            ),
            'first_reminder_after_days': (
                self.first_reminder_after_days
            ),
            'reminder_interval_days': (
                self.reminder_interval_days
            ),
            'escalation_days_before_due': (
                self.escalation_days_before_due
            ),
            'is_active': self.is_active,
            'next_run_at': (
                self.next_run_at.isoformat()
                if self.next_run_at
                else None
            ),
        }


class SignatureEvent(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_events'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )
    recipient_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_recipients.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
    )
    actor_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    event_type = db.Column(
        db.String(120),
        nullable=False,
        index=True,
    )
    description = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )
    occurred_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        index=True,
    )

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='events',
    )
    recipient = db.relationship(
        'SignatureRecipient',
        back_populates='events',
    )
    actor = db.relationship(
        'User',
        foreign_keys=[actor_user_id],
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(
                self.signature_request_id,
            ),
            'recipient_id': (
                str(self.recipient_id)
                if self.recipient_id
                else None
            ),
            'actor_user_id': (
                str(self.actor_user_id)
                if self.actor_user_id
                else None
            ),
            'event_type': self.event_type,
            'description': self.description,
            'metadata_json': self.metadata_json,
            'occurred_at': (
                self.occurred_at.isoformat()
                if self.occurred_at
                else None
            ),
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }
