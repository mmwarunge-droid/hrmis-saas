from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TenantMixin, TimestampMixin, uuid_pk


class Document(db.Model, TenantMixin, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'documents'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True)
    uploaded_by_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    title = db.Column(db.String(220), nullable=False)
    document_type = db.Column(db.String(80), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer)
    checksum_sha256 = db.Column(db.String(64))
    expiry_date = db.Column(db.Date, index=True)
    issued_date = db.Column(db.Date)
    signature_status = db.Column(db.String(40), nullable=False, default='not_required')
    access_level = db.Column(db.String(40), nullable=False, default='hr_only')
    status = db.Column(db.String(40), nullable=False, default='active')
    version = db.Column(db.Integer, nullable=False, default=1)

    employee = db.relationship('Employee', back_populates='documents')
    uploaded_by = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint("signature_status IN ('not_required','pending','signed','declined','expired')", name='ck_documents_signature_status'),
        db.CheckConstraint("access_level IN ('employee','manager','hr_only','company_admin')", name='ck_documents_access_level'),
        db.CheckConstraint("status IN ('active','archived','expired','pending_review')", name='ck_documents_status'),
    )

    def to_dict(self):
        return {
            'id': str(self.id), 'tenant_id': str(self.tenant_id),
            'employee_id': str(self.employee_id) if self.employee_id else None,
            'uploaded_by_id': str(self.uploaded_by_id) if self.uploaded_by_id else None,
            'title': self.title, 'document_type': self.document_type,
            'original_filename': self.original_filename, 'mime_type': self.mime_type,
            'size_bytes': self.size_bytes, 'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'signature_status': self.signature_status, 'access_level': self.access_level, 'status': self.status,
            'version': self.version,
        }
