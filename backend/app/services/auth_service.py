from app.extensions import db
from app.models import User
from app.services.rbac_service import seed_roles_permissions, set_user_roles
from app.utils.security import hash_password, verify_password
from app.models.base import utcnow


def claims_for(user: User) -> dict:
    return {'tenant_id': str(user.tenant_id) if user.tenant_id else None, 'roles': user.role_names, 'permissions': user.permission_codes}


def register_user(payload: dict, actor=None) -> User:
    if User.query.filter_by(email=payload['email'].lower()).first():
        raise ValueError('Email is already registered')
    seed_roles_permissions(commit=False)
    user = User(
        tenant_id=payload.get('tenant_id'),
        email=payload['email'].lower(),
        first_name=payload['first_name'],
        last_name=payload['last_name'],
        password_hash=hash_password(payload['password']),
    )
    db.session.add(user)
    db.session.flush()
    set_user_roles(user, payload.get('roles') or ['EMPLOYEE'], assigned_by_id=getattr(actor, 'id', None))
    db.session.commit()
    return user


def authenticate(email: str, password: str) -> User:
    user = User.query.filter(User.email == email.lower(), User.deleted_at.is_(None)).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise ValueError('Invalid email or password')
    user.last_login_at = utcnow()
    db.session.commit()
    return user
