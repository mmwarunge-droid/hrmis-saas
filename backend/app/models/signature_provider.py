from app.extensions import db
from app.models.base import (
    GUID,
    ReprMixin,
    TimestampMixin,
    utcnow,
    uuid_pk,
)


class SignatureArtifact(
    db.Model,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_artifacts'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(
        GUID(),
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='RESTRICT',
        ),
        nullable=False,
        index=True,
    )

    artifact_type = db.Column(
        db.String(40),
        nullable=False,
        index=True,
    )
    provider = db.Column(
        db.String(60),
        nullable=False,
        index=True,
    )
    provider_artifact_id = db.Column(
        db.String(255),
        nullable=True,
        index=True,
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False,
    )
    stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )
    file_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    checksum_sha256 = db.Column(
        db.String(64),
        nullable=False,
        index=True,
    )
    captured_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        index=True,
    )
    metadata_json = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='artifacts',
    )

    __table_args__ = (
        db.CheckConstraint(
            "artifact_type IN ("
            "'original_document','signed_document',"
            "'audit_trail','completion_certificate'"
            ")",
            name='ck_signature_artifacts_type',
        ),
        db.CheckConstraint(
            'size_bytes >= 0',
            name='ck_signature_artifacts_size',
        ),
        db.UniqueConstraint(
            'signature_request_id',
            'artifact_type',
            name='uq_signature_artifact_request_type',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(
                self.signature_request_id,
            ),
            'artifact_type': self.artifact_type,
            'provider': self.provider,
            'provider_artifact_id': self.provider_artifact_id,
            'original_filename': self.original_filename,
            'mime_type': self.mime_type,
            'size_bytes': self.size_bytes,
            'checksum_sha256': self.checksum_sha256,
            'captured_at': (
                self.captured_at.isoformat()
                if self.captured_at
                else None
            ),
            'metadata_json': self.metadata_json,
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }


class SignatureProviderEvent(
    db.Model,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_provider_events'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(
        GUID(),
        db.ForeignKey('tenants.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
    )

    provider = db.Column(
        db.String(60),
        nullable=False,
        index=True,
    )
    provider_event_id = db.Column(
        db.String(128),
        nullable=False,
    )
    provider_request_id = db.Column(
        db.String(255),
        nullable=True,
        index=True,
    )
    event_type = db.Column(
        db.String(120),
        nullable=False,
        index=True,
    )
    event_time = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )
    payload_sha256 = db.Column(
        db.String(64),
        nullable=False,
        index=True,
    )
    payload_json = db.Column(
        db.JSON,
        nullable=False,
    )
    signature_valid = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    processing_status = db.Column(
        db.String(30),
        nullable=False,
        default='pending',
        index=True,
    )
    processing_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )
    received_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        index=True,
    )
    processed_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='provider_events',
    )

    __table_args__ = (
        db.CheckConstraint(
            "processing_status IN ("
            "'pending','processed','ignored',"
            "'failed','unmatched'"
            ")",
            name='ck_signature_provider_events_status',
        ),
        db.CheckConstraint(
            'processing_attempts >= 0',
            name='ck_signature_provider_events_attempts',
        ),
        db.UniqueConstraint(
            'provider',
            'provider_event_id',
            name='uq_signature_provider_event',
        ),
    )

    def to_dict(self, include_payload=False):
        data = {
            'id': str(self.id),
            'tenant_id': (
                str(self.tenant_id)
                if self.tenant_id
                else None
            ),
            'signature_request_id': (
                str(self.signature_request_id)
                if self.signature_request_id
                else None
            ),
            'provider': self.provider,
            'provider_event_id': self.provider_event_id,
            'provider_request_id': self.provider_request_id,
            'event_type': self.event_type,
            'event_time': (
                self.event_time.isoformat()
                if self.event_time
                else None
            ),
            'payload_sha256': self.payload_sha256,
            'signature_valid': self.signature_valid,
            'processing_status': self.processing_status,
            'processing_attempts': self.processing_attempts,
            'received_at': (
                self.received_at.isoformat()
                if self.received_at
                else None
            ),
            'processed_at': (
                self.processed_at.isoformat()
                if self.processed_at
                else None
            ),
            'last_error': self.last_error,
        }

        if include_payload:
            data['payload_json'] = self.payload_json

        return data
