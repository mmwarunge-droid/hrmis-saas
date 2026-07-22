from functools import wraps

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


def tenant_query(model):
    """Return a model query scoped to the authenticated user's tenant unless SUPER_ADMIN."""
    if not current_user:
        raise RuntimeError('tenant_query requires an authenticated user')
    if current_user.has_role('SUPER_ADMIN'):
        return model.query
    if not hasattr(model, 'tenant_id'):
        raise RuntimeError(f'{model.__name__} is not tenant-scoped')
    return model.query.filter(model.tenant_id == current_user.tenant_id)


def require_same_tenant(tenant_id):
    if current_user.has_role('SUPER_ADMIN'):
        return True
    return str(current_user.tenant_id) == str(tenant_id)
