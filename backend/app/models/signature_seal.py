from app.extensions import db
from app.models.base import (
    GUID,
    ReprMixin,
    TimestampMixin,
    utcnow,
    uuid_pk,
)


class SignatureSeal(
    db.Model,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'signature_seals'

    id = db.Column(
        GUID(),
        primary_key=True,
        default=uuid_pk,
    )
    tenant_id = db.Column(
        GUID(),
        db.ForeignKey(
            'tenants.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )
    signature_request_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_requests.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    uploaded_by_id = db.Column(
        GUID(),
        db.ForeignKey(
            'users.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
    )
    applied_by_id = db.Column(
        GUID(),
        db.ForeignKey(
            'users.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
    )
    sealed_artifact_id = db.Column(
        GUID(),
        db.ForeignKey(
            'signature_artifacts.id',
            ondelete='SET NULL',
        ),
        nullable=True,
        unique=True,
    )

    image_original_filename = db.Column(
        db.String(255),
        nullable=False,
    )
    image_stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )
    image_file_path = db.Column(
        db.Text,
        nullable=False,
    )
    image_mime_type = db.Column(
        db.String(120),
        nullable=False,
    )
    image_size_bytes = db.Column(
        db.Integer,
        nullable=False,
    )
    image_sha256 = db.Column(
        db.String(64),
        nullable=False,
        index=True,
    )

    page_number = db.Column(
        db.Integer,
        nullable=True,
    )
    x = db.Column(
        db.Float,
        nullable=True,
    )
    y = db.Column(
        db.Float,
        nullable=True,
    )
    width = db.Column(
        db.Float,
        nullable=True,
    )
    height = db.Column(
        db.Float,
        nullable=True,
    )

    uploaded_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        index=True,
    )
    applied_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )

    signature_request = db.relationship(
        'SignatureRequest',
        back_populates='seal',
    )
    uploaded_by = db.relationship(
        'User',
        foreign_keys=[uploaded_by_id],
    )
    applied_by = db.relationship(
        'User',
        foreign_keys=[applied_by_id],
    )
    sealed_artifact = db.relationship(
        'SignatureArtifact',
        foreign_keys=[sealed_artifact_id],
    )

    __table_args__ = (
        db.UniqueConstraint(
            'signature_request_id',
            name='uq_signature_seals_request',
        ),
        db.CheckConstraint(
            "image_mime_type IN ("
            "'image/png','image/jpeg','image/webp'"
            ")",
            name='ck_signature_seals_image_mime',
        ),
        db.CheckConstraint(
            'image_size_bytes >= 0',
            name='ck_signature_seals_image_size',
        ),
        db.CheckConstraint(
            'page_number IS NULL OR page_number >= 1',
            name='ck_signature_seals_page',
        ),
        db.CheckConstraint(
            'x IS NULL OR (x >= 0 AND x <= 1)',
            name='ck_signature_seals_x',
        ),
        db.CheckConstraint(
            'y IS NULL OR (y >= 0 AND y <= 1)',
            name='ck_signature_seals_y',
        ),
        db.CheckConstraint(
            'width IS NULL OR (width > 0 AND width <= 1)',
            name='ck_signature_seals_width',
        ),
        db.CheckConstraint(
            'height IS NULL OR (height > 0 AND height <= 1)',
            name='ck_signature_seals_height',
        ),
        db.CheckConstraint(
            'x IS NULL OR width IS NULL OR x + width <= 1',
            name='ck_signature_seals_horizontal_bounds',
        ),
        db.CheckConstraint(
            'y IS NULL OR height IS NULL OR y + height <= 1',
            name='ck_signature_seals_vertical_bounds',
        ),
        db.CheckConstraint(
            "("
            "applied_at IS NULL "
            "AND sealed_artifact_id IS NULL"
            ") OR ("
            "applied_at IS NOT NULL "
            "AND sealed_artifact_id IS NOT NULL"
            ")",
            name='ck_signature_seals_application_state',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'signature_request_id': str(
                self.signature_request_id,
            ),
            'uploaded_by_id': (
                str(self.uploaded_by_id)
                if self.uploaded_by_id
                else None
            ),
            'applied_by_id': (
                str(self.applied_by_id)
                if self.applied_by_id
                else None
            ),
            'sealed_artifact_id': (
                str(self.sealed_artifact_id)
                if self.sealed_artifact_id
                else None
            ),
            'image_original_filename': (
                self.image_original_filename
            ),
            'image_mime_type': self.image_mime_type,
            'image_size_bytes': self.image_size_bytes,
            'image_sha256': self.image_sha256,
            'page_number': self.page_number,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'uploaded_at': (
                self.uploaded_at.isoformat()
                if self.uploaded_at
                else None
            ),
            'applied_at': (
                self.applied_at.isoformat()
                if self.applied_at
                else None
            ),
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
