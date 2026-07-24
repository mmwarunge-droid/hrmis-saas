import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime) -> datetime:
    """Normalize aware or naive datetimes to naive UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class GUID(TypeDecorator):
    """Platform-independent UUID type: native UUID on PostgreSQL, CHAR(36) elsewhere."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value if dialect.name == 'postgresql' else str(value)
        parsed = uuid.UUID(str(value))
        return parsed if dialect.name == 'postgresql' else str(parsed)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def uuid_pk():
    return uuid.uuid4()


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    def soft_delete(self):
        self.deleted_at = utcnow()


class TenantMixin:
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)


class ReprMixin:
    def __repr__(self):
        return f'<{self.__class__.__name__} {getattr(self, "id", None)}>'
