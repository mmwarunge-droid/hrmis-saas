from flask_jwt_extended import current_user

from app.extensions import db
from app.models import AuditLog
from app.utils.request_security import privacy_safe_request_metadata, security_fingerprint

_UNSET = object()


def _current_actor():
    try:
        return current_user if current_user and getattr(current_user, 'id', None) else None
    except RuntimeError:
        return None


def identifier_fingerprint(identifier: str | None) -> str | None:
    return security_fingerprint(identifier, 'authentication-identifier')


def log_event(
    action: str,
    entity_type: str,
    entity_id=None,
    tenant_id=None,
    metadata=None,
    actor=_UNSET,
):
    resolved_actor = _current_actor() if actor is _UNSET else actor
    ip_address, user_agent = privacy_safe_request_metadata()
    log = AuditLog(
        tenant_id=tenant_id if tenant_id is not None else getattr(resolved_actor, 'tenant_id', None),
        actor_user_id=getattr(resolved_actor, 'id', None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=metadata or {},
    )
    db.session.add(log)
    return log
