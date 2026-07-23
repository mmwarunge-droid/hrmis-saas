import hashlib
import logging
import secrets
from datetime import datetime, timezone

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from sqlalchemy import select

from app.extensions import db, redis_store
from app.models import AuthSession, User
from app.models.base import utcnow
from app.services.auth_service import claims_for
from app.utils.request_security import anonymize_ip_address, user_agent_family

logger = logging.getLogger(__name__)


class SessionRevokedError(ValueError):
    pass


class RefreshTokenReuseError(ValueError):
    pass


def _hash_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode('utf-8')).hexdigest()


def _expires_at(token: str) -> datetime:
    return datetime.fromtimestamp(decode_token(token)['exp'], tz=timezone.utc).replace(tzinfo=None)


def _redis_key(kind: str, value: str) -> str:
    prefix = current_app.config['REDIS_KEY_PREFIX'].rstrip(':')
    return f'{prefix}:{kind}:{value}'


def _ttl_seconds(expires_at: datetime) -> int:
    return max(int((expires_at - utcnow()).total_seconds()), 1)


def _redis_get(key: str):
    try:
        return redis_store.client.get(key)
    except Exception:
        logger.exception('Redis read failed; database session state remains authoritative')
        return None


def _redis_set(key: str, value: str, expires_at: datetime) -> None:
    try:
        redis_store.client.set(key, value, ex=_ttl_seconds(expires_at))
    except Exception:
        logger.exception('Redis revocation write failed; database session state remains authoritative')


def _issue_tokens(user: User, auth_session: AuthSession) -> tuple[str, str, str]:
    claims = claims_for(user)
    claims['sid'] = str(auth_session.id)
    claims['mfa_verified'] = auth_session.mfa_verified_at is not None
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)
    refresh_jti = decode_token(refresh_token)['jti']
    return access_token, refresh_token, refresh_jti


def create_auth_session(user: User, ip_address=None, user_agent=None, mfa_verified: bool = False):
    provisional_hash = secrets.token_hex(32)
    auth_session = AuthSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        refresh_jti_hash=provisional_hash,
        expires_at=utcnow(),
        last_seen_at=utcnow(),
        ip_address=(ip_address or '')[:80] or None,
        user_agent=(user_agent or '')[:255] or None,
        mfa_verified_at=utcnow() if mfa_verified else None,
    )
    db.session.add(auth_session)
    db.session.flush()

    access_token, refresh_token, refresh_jti = _issue_tokens(user, auth_session)
    auth_session.refresh_jti_hash = _hash_jti(refresh_jti)
    auth_session.expires_at = _expires_at(refresh_token)
    db.session.commit()
    return auth_session, access_token, refresh_token


def rotate_auth_session(user: User, jwt_data: dict):
    session_id = jwt_data.get('sid')
    refresh_jti = jwt_data.get('jti')
    if not session_id or not refresh_jti:
        raise SessionRevokedError('The authentication session is invalid')

    auth_session = db.session.execute(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    ).scalar_one_or_none()

    if (
        not auth_session
        or str(auth_session.user_id) != str(user.id)
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= utcnow()
    ):
        raise SessionRevokedError('The authentication session is no longer active')

    if auth_session.refresh_jti_hash != _hash_jti(refresh_jti):
        revoke_session(auth_session, 'refresh_token_reuse', token_jti=refresh_jti)
        db.session.commit()
        raise RefreshTokenReuseError('Refresh token reuse was detected; the session has been revoked')

    access_token, refresh_token, new_refresh_jti = _issue_tokens(user, auth_session)
    auth_session.refresh_jti_hash = _hash_jti(new_refresh_jti)
    auth_session.expires_at = _expires_at(refresh_token)
    auth_session.last_seen_at = utcnow()
    db.session.commit()
    return auth_session, access_token, refresh_token


def revoke_session(auth_session: AuthSession, reason: str, token_jti=None, token_expires_at=None) -> None:
    if auth_session.revoked_at is None:
        auth_session.revoked_at = utcnow()
        auth_session.revoked_reason = reason

    _redis_set(_redis_key('session', str(auth_session.id)), reason, auth_session.expires_at)
    if token_jti:
        _redis_set(
            _redis_key('jti', token_jti),
            reason,
            token_expires_at or auth_session.expires_at,
        )


def revoke_session_from_token(jwt_data: dict, reason: str):
    auth_session = get_session_for_token(jwt_data, lock=True)
    if auth_session:
        token_expires_at = datetime.fromtimestamp(jwt_data['exp'], tz=timezone.utc).replace(tzinfo=None)
        revoke_session(auth_session, reason, jwt_data.get('jti'), token_expires_at)
        db.session.commit()
    return auth_session


def revoke_all_user_sessions(user: User, reason: str, jwt_data=None, commit: bool = True) -> int:
    sessions = AuthSession.query.filter(
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > utcnow(),
    ).all()

    for auth_session in sessions:
        revoke_session(auth_session, reason)

    if jwt_data and jwt_data.get('jti'):
        token_expires_at = datetime.fromtimestamp(jwt_data['exp'], tz=timezone.utc).replace(tzinfo=None)
        _redis_set(_redis_key('jti', jwt_data['jti']), reason, token_expires_at)

    if commit:
        db.session.commit()
    return len(sessions)


def get_session_for_token(jwt_data: dict, lock=False):
    session_id = jwt_data.get('sid')
    if not session_id:
        return None
    statement = select(AuthSession).where(AuthSession.id == session_id)
    if lock:
        statement = statement.with_for_update()
    return db.session.execute(statement).scalar_one_or_none()


def list_user_sessions(user: User):
    return AuthSession.query.filter_by(user_id=user.id).order_by(AuthSession.created_at.desc()).limit(100).all()


def detect_login_risk(user: User, ip_address=None, user_agent=None) -> list[str]:
    if not current_app.config.get('AUTH_SUSPICIOUS_LOGIN_ENABLED'):
        return []

    previous_sessions = (
        AuthSession.query.filter(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc())
        .limit(20)
        .all()
    )
    if not previous_sessions:
        return []

    flags = []
    current_network = anonymize_ip_address(ip_address)
    known_networks = {anonymize_ip_address(session.ip_address) for session in previous_sessions if session.ip_address}
    if current_network and known_networks and current_network not in known_networks:
        flags.append('new_network')

    current_agent = user_agent_family(user_agent)
    known_agents = {user_agent_family(session.user_agent) for session in previous_sessions if session.user_agent}
    if current_agent != 'unknown' and known_agents and current_agent not in known_agents:
        flags.append('new_user_agent')

    return flags


def is_token_revoked(jwt_data: dict) -> bool:
    jti = jwt_data.get('jti')
    session_id = jwt_data.get('sid')
    if not jti or not session_id:
        return True

    if _redis_get(_redis_key('jti', jti)) is not None:
        return True
    if _redis_get(_redis_key('session', session_id)) is not None:
        return True

    auth_session = get_session_for_token(jwt_data)
    if not auth_session:
        return True
    if str(auth_session.user_id) != str(jwt_data.get('sub')):
        return True
    if auth_session.revoked_at is not None or auth_session.expires_at <= utcnow():
        return True

    user = db.session.get(User, auth_session.user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        return True

    from app.services.mfa_service import is_mfa_required

    mfa_needed = user.mfa_enabled_at is not None or is_mfa_required(user)
    if mfa_needed and (not jwt_data.get('mfa_verified') or auth_session.mfa_verified_at is None):
        return True
    return False
