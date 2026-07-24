from app.extensions import db
from app.models.base import GUID, ReprMixin, TimestampMixin, to_utc_naive, utcnow, uuid_pk


class AuthSession(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'auth_sessions'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    refresh_jti_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    revoked_reason = db.Column(db.String(120), nullable=True)
    ip_address = db.Column(db.String(80), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    mfa_verified_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship('User', back_populates='auth_sessions')
    tenant = db.relationship('Tenant')

    @property
    def is_active(self):
        return self.revoked_at is None and to_utc_naive(self.expires_at) > utcnow()

    def to_dict(self, current_session_id=None):
        return {
            'id': str(self.id),
            'current': str(self.id) == str(current_session_id),
            'active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'revoked_reason': self.revoked_reason,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'mfa_verified': self.mfa_verified_at is not None,
            'mfa_verified_at': self.mfa_verified_at.isoformat() if self.mfa_verified_at else None,
        }
