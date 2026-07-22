from app.extensions import db
from app.models.base import GUID, ReprMixin, TimestampMixin, uuid_pk


class AuditLog(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'audit_logs'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    actor_user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(GUID(), nullable=True, index=True)
    ip_address = db.Column(db.String(80))
    user_agent = db.Column(db.String(255))
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    actor = db.relationship('User')

    def to_dict(self):
        return {'id': str(self.id), 'tenant_id': str(self.tenant_id) if self.tenant_id else None, 'actor_user_id': str(self.actor_user_id) if self.actor_user_id else None, 'action': self.action, 'entity_type': self.entity_type, 'entity_id': str(self.entity_id) if self.entity_id else None, 'metadata_json': self.metadata_json, 'created_at': self.created_at.isoformat() if self.created_at else None}


class Notification(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'notifications'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text)
    notification_type = db.Column(db.String(80), nullable=False, default='system')
    read_at = db.Column(db.DateTime)

    user = db.relationship('User', back_populates='notifications')

    def to_dict(self):
        return {'id': str(self.id), 'tenant_id': str(self.tenant_id), 'user_id': str(self.user_id), 'title': self.title, 'body': self.body, 'notification_type': self.notification_type, 'read_at': self.read_at.isoformat() if self.read_at else None}
