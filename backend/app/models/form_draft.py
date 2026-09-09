from app.extensions import db
from app.models.base import GUID, TimestampMixin, uuid_pk


class FormDraft(db.Model, TimestampMixin):
    """Private, tenant-scoped work in progress. Saving never executes a workflow."""
    __tablename__ = 'form_drafts'
    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    owner_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    scope_key = db.Column(db.String(36), nullable=False)
    workflow_key = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(220), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=1)
    data = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint('owner_id', 'scope_key', 'workflow_key', name='uq_form_draft_owner_scope_key'),)

    def to_dict(self, include_data=True):
        result = {'key': self.workflow_key, 'title': self.title, 'revision': self.revision,
                  'updated_at': self.updated_at.isoformat() + 'Z', 'status': 'draft'}
        if include_data:
            result['data'] = self.data
        return result
