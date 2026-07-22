from flask import request
from flask_jwt_extended import current_user

from app.extensions import db
from app.models import AuditLog


def log_event(action: str, entity_type: str, entity_id=None, tenant_id=None, metadata=None):
    actor = current_user if current_user else None
    log = AuditLog(
        tenant_id=tenant_id if tenant_id is not None else getattr(actor, 'tenant_id', None),
        actor_user_id=getattr(actor, 'id', None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=request.headers.get('X-Forwarded-For', request.remote_addr) if request else None,
        user_agent=request.headers.get('User-Agent') if request else None,
        metadata_json=metadata or {},
    )
    db.session.add(log)
    return log
