from app.extensions import db
from app.models.base import GUID, ReprMixin, TimestampMixin, utcnow, uuid_pk


class AccountToken(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'account_tokens'

    PURPOSE_PASSWORD_RESET = 'password_reset'
    PURPOSE_EMAIL_VERIFICATION = 'email_verification'
    PURPOSES = {PURPOSE_PASSWORD_RESET, PURPOSE_EMAIL_VERIFICATION}

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    purpose = db.Column(db.String(40), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    consumed_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship('User', back_populates='account_tokens')

    __table_args__ = (
        db.CheckConstraint(
            "purpose IN ('password_reset','email_verification')",
            name='ck_account_tokens_purpose',
        ),
        db.Index(
            'ix_account_tokens_user_purpose_active',
            'user_id',
            'purpose',
            'consumed_at',
            'expires_at',
        ),
    )

    @property
    def active(self) -> bool:
        return self.consumed_at is None and self.expires_at > utcnow()
