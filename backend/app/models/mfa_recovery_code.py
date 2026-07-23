from app.extensions import db
from app.models.base import GUID, ReprMixin, TimestampMixin, uuid_pk


class MfaRecoveryCode(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'mfa_recovery_codes'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True)
    used_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship('User', back_populates='mfa_recovery_codes')

    __table_args__ = (
        db.Index('ix_mfa_recovery_codes_user_unused', 'user_id', 'used_at'),
    )
