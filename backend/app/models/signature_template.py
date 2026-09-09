from app.extensions import db
from app.models.base import GUID, TenantMixin, TimestampMixin, uuid_pk


class SignatureTemplate(db.Model, TenantMixin, TimestampMixin):
    __tablename__ = "signature_templates"
    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(220), nullable=False)
    document_id = db.Column(GUID(), db.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    source_checksum = db.Column(db.String(64), nullable=False)
    definition = db.Column(db.JSON, nullable=False)
    document = db.relationship("Document")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "document_id": str(self.document_id),
            "definition": self.definition,
            "tenant_id": str(self.tenant_id),
        }
