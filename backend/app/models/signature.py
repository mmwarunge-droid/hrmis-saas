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
    resend_of_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
    )
    resend_attempt = db.Column(
        db.Integer,
        nullable=False,
        default=0,
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
    evidence_status = db.Column(
        db.String(30),
        nullable=False,
        default='not_required',
        index=True,
    )
    evidence_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )
    evidence_next_attempt_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )
    evidence_last_attempt_at = db.Column(
        db.DateTime,
        nullable=True,
    )
    evidence_locked_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )
    evidence_last_error = db.Column(
        db.Text,
        nullable=True,
    )
    evidence_verification_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )

    document = db.relationship('Document')
    created_by = db.relationship(
        'User',
        foreign_keys=[created_by_id],
    )
    resend_of_request = db.relationship(
        'SignatureRequest',
        remote_side='SignatureRequest.id',
        foreign_keys=[resend_of_request_id],
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
    fields = db.relationship(
        'SignatureField',
        back_populates='signature_request',
        cascade='all, delete-orphan',
        order_by='SignatureField.page_number',
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
            'resend_attempt >= 0',
            name='ck_signature_requests_resend_attempt',
        ),
        db.CheckConstraint(
            "assurance_level IS NULL OR "
            "assurance_level IN ('standard','aes','qes')",
            name='ck_signature_requests_assurance_level',
        ),
        db.CheckConstraint(
            "evidence_status IN ("
            "'not_required','awaiting_provider','pending',"
            "'processing','retry_scheduled','verified','failed'"
            ")",
            name='ck_signature_requests_evidence_status',
        ),
        db.CheckConstraint(
            'evidence_attempts >= 0',
            name='ck_signature_requests_evidence_attempts',
        ),
        db.Index(
            'ix_signature_requests_evidence_queue',
            'evidence_status',
            'evidence_next_attempt_at',
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
            'resend_of_request_id': (
                str(self.resend_of_request_id)
                if self.resend_of_request_id
                else None
            ),
            'resend_attempt': self.resend_attempt,
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
            'evidence_status': self.evidence_status,
            'evidence_attempts': self.evidence_attempts,
            'evidence_next_attempt_at': (
                self.evidence_next_attempt_at.isoformat()
                if self.evidence_next_attempt_at
                else None
            ),
            'evidence_last_attempt_at': (
                self.evidence_last_attempt_at.isoformat()
                if self.evidence_last_attempt_at
                else None
            ),
            'evidence_last_error': self.evidence_last_error,
            'evidence_verification_json': (
                self.evidence_verification_json
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
    signature_name = db.Column(db.String(240), nullable=True)
    signature_method = db.Column(db.String(40), nullable=True)
    signature_style = db.Column(db.String(40), nullable=True)
    consented_at = db.Column(db.DateTime, nullable=True)
    consent_version = db.Column(db.String(40), nullable=True)
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
    fields = db.relationship(
        'SignatureField',
        back_populates='recipient',
        cascade='all, delete-orphan',
        order_by='SignatureField.page_number',
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
            'signature_name': self.signature_name,
            'signature_method': self.signature_method,
            'signature_style': self.signature_style,
            'consented_at': (
                self.consented_at.isoformat()
                if self.consented_at
                else None
            ),
            'consent_version': self.consent_version,
            'provider_recipient_id': (
                self.provider_recipient_id
            ),
            'provider_status': self.provider_status,
            'provider_metadata_json': (
                self.provider_metadata_json
            ),
        }


class SignatureField(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    """A recipient-owned field positioned on a PDF page.

    Coordinates are normalized to the page using a top-left origin so the
    same values can be used by the React overlay and translated to PDF points
    by the server-side renderer.
    """

    __tablename__ = 'signature_fields'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey('signature_requests.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    recipient_id = db.Column(
        GUID(),
        db.ForeignKey('signature_recipients.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    field_type = db.Column(db.String(30), nullable=False, index=True)
    label = db.Column(db.String(160), nullable=True)
    placeholder = db.Column(db.String(240), nullable=True)
    prefill_key = db.Column(db.String(80), nullable=True)
    page_number = db.Column(db.Integer, nullable=False, default=1)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    required = db.Column(db.Boolean, nullable=False, default=True)
    value = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='fields',
    )
    recipient = db.relationship(
        'SignatureRecipient',
        back_populates='fields',
    )

    __table_args__ = (
        db.CheckConstraint(
            "field_type IN ('signature','date','text','name','initials')",
            name='ck_signature_fields_type',
        ),
        db.CheckConstraint(
            'page_number >= 1',
            name='ck_signature_fields_page_number',
        ),
        db.CheckConstraint(
            'x >= 0 AND x <= 1 AND y >= 0 AND y <= 1',
            name='ck_signature_fields_origin',
        ),
        db.CheckConstraint(
            'width > 0 AND width <= 1 AND height > 0 AND height <= 1',
            name='ck_signature_fields_dimensions',
        ),
        db.CheckConstraint(
            'x + width <= 1 AND y + height <= 1',
            name='ck_signature_fields_page_bounds',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(self.signature_request_id),
            'recipient_id': str(self.recipient_id),
            'field_type': self.field_type,
            'label': self.label,
            'placeholder': self.placeholder,
            'prefill_key': self.prefill_key,
            'page_number': self.page_number,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'required': self.required,
            'value': self.value,
            'completed_at': (
                self.completed_at.isoformat()
                if self.completed_at
                else None
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


class SignatureDiscussion(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_discussions'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey('signature_requests.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    recipient_id = db.Column(
        GUID(),
        db.ForeignKey('signature_recipients.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default='open', index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_user_id = db.Column(
        GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    signature_request = db.relationship('SignatureRequest')
    recipient = db.relationship('SignatureRecipient')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_user_id])
    comments = db.relationship(
        'SignatureDiscussionComment',
        back_populates='discussion',
        cascade='all, delete-orphan',
        order_by='SignatureDiscussionComment.created_at',
    )
    participants = db.relationship(
        'SignatureDiscussionParticipant',
        back_populates='discussion',
        passive_deletes=True,
        order_by='SignatureDiscussionParticipant.created_at',
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('open','resolved')",
            name='ck_signature_discussions_status',
        ),
        db.UniqueConstraint(
            'signature_request_id',
            'recipient_id',
            name='uq_signature_discussion_request_recipient',
        ),
    )

    def to_dict(self, include_comments=True):
        data = {
            'id': str(self.id),
            'signature_request_id': str(self.signature_request_id),
            'recipient_id': str(self.recipient_id) if self.recipient_id else None,
            'subject': (
                self.signature_request.subject
                if self.signature_request
                else 'Document discussion'
            ),
            'signer_name': (
                self.recipient.name
                if self.recipient
                else None
            ),
            'status': self.status,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by_user_id': (
                str(self.resolved_by_user_id) if self.resolved_by_user_id else None
            ),
        }
        if include_comments:
            data['comments'] = [comment.to_dict() for comment in self.comments]
        return data


class SignatureDiscussionComment(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_discussion_comments'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    discussion_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_discussions.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )
    author_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    body = db.Column(db.Text, nullable=False)
    mentioned_user_ids_json = db.Column(
        db.JSON,
        nullable=False,
        default=list,
    )
    edited_at = db.Column(
        db.DateTime,
        nullable=True,
    )
    deleted_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )
    deleted_by_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )

    discussion = db.relationship(
        'SignatureDiscussion',
        back_populates='comments',
    )
    author = db.relationship(
        'User',
        foreign_keys=[author_user_id],
    )
    deleted_by = db.relationship(
        'User',
        foreign_keys=[deleted_by_user_id],
    )
    revisions = db.relationship(
        'SignatureDiscussionCommentRevision',
        back_populates='comment',
        passive_deletes=True,
        order_by='SignatureDiscussionCommentRevision.occurred_at',
    )

    def to_dict(self):
        deleted = self.deleted_at is not None
        return {
            'id': str(self.id),
            'discussion_id': str(self.discussion_id),
            'author_user_id': (
                str(self.author_user_id)
                if self.author_user_id
                else None
            ),
            'author_name': (
                self.author.full_name
                if self.author
                else 'Former user'
            ),
            'body': None if deleted else self.body,
            'mentioned_user_ids': (
                []
                if deleted
                else list(self.mentioned_user_ids_json or [])
            ),
            'is_deleted': deleted,
            'edited_at': (
                self.edited_at.isoformat()
                if self.edited_at
                else None
            ),
            'deleted_at': (
                self.deleted_at.isoformat()
                if self.deleted_at
                else None
            ),
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }


class SignatureDiscussionParticipant(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_discussion_participants'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    discussion_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_discussions.id',
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
    added_by_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    source = db.Column(
        db.String(30),
        nullable=False,
        default='mention',
    )

    discussion = db.relationship(
        'SignatureDiscussion',
        back_populates='participants',
    )
    user = db.relationship(
        'User',
        foreign_keys=[user_id],
    )
    added_by = db.relationship(
        'User',
        foreign_keys=[added_by_user_id],
    )

    __table_args__ = (
        db.CheckConstraint(
            "source IN ('mention','manual')",
            name='ck_signature_discussion_participants_source',
        ),
        db.UniqueConstraint(
            'discussion_id',
            'user_id',
            name='uq_signature_discussion_participant_user',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'discussion_id': str(self.discussion_id),
            'user_id': (
                str(self.user_id)
                if self.user_id
                else None
            ),
            'name': (
                self.user.full_name
                if self.user
                else 'Former user'
            ),
            'source': self.source,
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }


class SignatureDiscussionCommentRevision(
    db.Model,
    TenantMixin,
    ReprMixin,
):
    __tablename__ = 'signature_discussion_comment_revisions'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    comment_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_discussion_comments.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )
    actor_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    revision_type = db.Column(
        db.String(20),
        nullable=False,
    )
    body = db.Column(
        db.Text,
        nullable=False,
    )
    mentioned_user_ids_json = db.Column(
        db.JSON,
        nullable=False,
        default=list,
    )
    occurred_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        index=True,
    )

    comment = db.relationship(
        'SignatureDiscussionComment',
        back_populates='revisions',
    )
    actor = db.relationship(
        'User',
        foreign_keys=[actor_user_id],
    )

    __table_args__ = (
        db.CheckConstraint(
            "revision_type IN ('created','edited','deleted')",
            name='ck_signature_discussion_revision_type',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'comment_id': str(self.comment_id),
            'actor_user_id': (
                str(self.actor_user_id)
                if self.actor_user_id
                else None
            ),
            'revision_type': self.revision_type,
            'body': self.body,
            'mentioned_user_ids': list(
                self.mentioned_user_ids_json or []
            ),
            'occurred_at': (
                self.occurred_at.isoformat()
                if self.occurred_at
                else None
            ),
        }
