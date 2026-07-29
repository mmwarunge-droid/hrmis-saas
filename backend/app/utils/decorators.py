from functools import wraps

from flask import request
from flask_jwt_extended import current_user, verify_jwt_in_request

from app.utils.response import fail


def role_required(*roles):
    def outer(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not current_user or not current_user.has_any_role(set(roles)):
                return fail('FORBIDDEN', 'Insufficient role privileges', 403)
            return fn(*args, **kwargs)
        return wrapper
    return outer


def permission_required(*permissions):
    def outer(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not current_user or not current_user.has_permissions(set(permissions)):
                return fail('FORBIDDEN', 'Insufficient permissions', 403)
            return fn(*args, **kwargs)
        return wrapper
    return outer


def request_tenant_id(payload=None):
    """Resolve the active tenant for the current request."""
    if not current_user:
        raise RuntimeError(
            'request_tenant_id requires an authenticated user'
        )

    if current_user.has_role('SUPER_ADMIN'):
        payload_tenant_id = None
        if payload is not None:
            payload_tenant_id = payload.pop('tenant_id', None)

        return payload_tenant_id or request.args.get('tenant_id')

    if payload is not None:
        payload.pop('tenant_id', None)

    return current_user.tenant_id


def tenant_query(model):
    """Return a tenant-scoped model query for the current request."""
    if not current_user:
        raise RuntimeError(
            'tenant_query requires an authenticated user'
        )
    if not hasattr(model, 'tenant_id'):
        raise RuntimeError(f'{model.__name__} is not tenant-scoped')

    if current_user.has_role('SUPER_ADMIN'):
        tenant_id = request.args.get('tenant_id')
        if tenant_id:
            return model.query.filter(model.tenant_id == tenant_id)
        return model.query

    return model.query.filter(
        model.tenant_id == current_user.tenant_id
    )


def require_same_tenant(tenant_id):
    if current_user.has_role('SUPER_ADMIN'):
        return True
    return str(current_user.tenant_id) == str(tenant_id)
