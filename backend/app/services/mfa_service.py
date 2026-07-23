import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from io import BytesIO

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from flask import current_app
from pyotp.utils import strings_equal
from qrcode.image.svg import SvgPathImage
from sqlalchemy import delete, select

from app.extensions import db, redis_store
from app.models import MfaRecoveryCode, User
from app.models.base import utcnow
from app.utils.security import verify_password


class MfaError(ValueError):
    public_message = 'Multi-factor authentication could not be completed'

    def __init__(self, reason: str, attempts_remaining: int | None = None):
        super().__init__(self.public_message)
        self.reason = reason
        self.attempts_remaining = attempts_remaining


class MfaConfigurationError(RuntimeError):
    pass


def _required_roles() -> set[str]:
    return set(current_app.config.get('MFA_REQUIRED_ROLES') or [])


def is_mfa_required(user: User) -> bool:
    return bool(_required_roles().intersection(user.role_names))


def _fernet() -> MultiFernet:
    try:
        return MultiFernet([Fernet(key.encode('ascii')) for key in current_app.config['MFA_ENCRYPTION_KEYS']])
    except (KeyError, ValueError, TypeError) as exc:
        raise MfaConfigurationError('MFA encryption keys are invalid') from exc


def _encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode('ascii')).decode('ascii')


def _decrypt_secret(ciphertext: str | None) -> str:
    if not ciphertext:
        raise MfaError('mfa_not_configured')
    try:
        return _fernet().decrypt(ciphertext.encode('ascii')).decode('ascii')
    except (InvalidToken, ValueError, TypeError) as exc:
        raise MfaConfigurationError('The stored MFA secret cannot be decrypted') from exc


def _challenge_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _redis_key(kind: str, value: str) -> str:
    prefix = current_app.config['REDIS_KEY_PREFIX'].rstrip(':')
    return f'{prefix}:mfa:{kind}:{value}'


def _challenge_seconds() -> int:
    return max(int(current_app.config['MFA_CHALLENGE_MINUTES']) * 60, 60)


def issue_mfa_challenge(user: User, purpose: str, ip_address=None, user_agent=None) -> str:
    if purpose not in {'verify', 'enroll'}:
        raise ValueError('Unsupported MFA challenge purpose')

    raw_token = secrets.token_urlsafe(32)
    payload = {
        'user_id': str(user.id),
        'purpose': purpose,
        'attempts': 0,
        'ip_address': (ip_address or '')[:80] or None,
        'user_agent': (user_agent or '')[:255] or None,
    }
    redis_store.client.set(
        _redis_key('challenge', _challenge_digest(raw_token)),
        json.dumps(payload, separators=(',', ':')),
        ex=_challenge_seconds(),
    )
    return raw_token


def _load_challenge(raw_token: str, expected_purpose: str | None = None) -> tuple[dict, User]:
    if not raw_token:
        raise MfaError('invalid_challenge')

    key = _redis_key('challenge', _challenge_digest(raw_token))
    raw_payload = redis_store.client.get(key)
    if not raw_payload:
        raise MfaError('invalid_or_expired_challenge')

    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError) as exc:
        redis_store.client.delete(key)
        raise MfaError('invalid_challenge') from exc

    if expected_purpose and payload.get('purpose') != expected_purpose:
        raise MfaError('invalid_challenge_purpose')

    user = db.session.get(User, payload.get('user_id'))
    if not user or not user.is_active or user.deleted_at is not None:
        redis_store.client.delete(key)
        raise MfaError('invalid_challenge_user')
    return payload, user


def _record_challenge_failure(raw_token: str, payload: dict) -> int:
    attempts = int(payload.get('attempts') or 0) + 1
    maximum = max(int(current_app.config['MFA_MAX_CHALLENGE_ATTEMPTS']), 1)
    key = _redis_key('challenge', _challenge_digest(raw_token))
    if attempts >= maximum:
        redis_store.client.delete(key)
        return 0

    payload['attempts'] = attempts
    redis_store.client.set(key, json.dumps(payload, separators=(',', ':')), ex=_challenge_seconds())
    return maximum - attempts


def _consume_challenge(raw_token: str) -> None:
    digest = _challenge_digest(raw_token)
    claim_key = _redis_key('consumed', digest)
    if not redis_store.client.set(claim_key, '1', ex=_challenge_seconds(), nx=True):
        raise MfaError('challenge_already_used')
    redis_store.client.delete(_redis_key('challenge', digest))


def _totp_match(secret: str, code: str, last_used_timecode: int | None = None) -> int | None:
    normalized = ''.join(character for character in str(code or '') if character.isdigit())
    if len(normalized) != 6:
        return None

    totp = pyotp.TOTP(secret)
    now = datetime.now(timezone.utc)
    current_timecode = totp.timecode(now)
    window = max(int(current_app.config['MFA_TOTP_VALID_WINDOW']), 0)

    for offset in range(-window, window + 1):
        timecode = current_timecode + offset
        if timecode < 0 or (last_used_timecode is not None and timecode <= last_used_timecode):
            continue
        if strings_equal(totp.generate_otp(timecode), normalized):
            return timecode
    return None


def _recovery_code_hash(code: str) -> str:
    normalized = ''.join(character for character in str(code or '').upper() if character.isalnum())
    pepper = current_app.config['MFA_RECOVERY_CODE_PEPPER'].encode('utf-8')
    return hmac.new(pepper, normalized.encode('ascii', errors='ignore'), hashlib.sha256).hexdigest()


def _new_recovery_code() -> str:
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    raw = ''.join(secrets.choice(alphabet) for _ in range(12))
    return '-'.join(raw[index:index + 4] for index in range(0, 12, 4))


def generate_recovery_codes(user: User) -> list[str]:
    db.session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    count = max(int(current_app.config['MFA_RECOVERY_CODE_COUNT']), 1)
    codes = [_new_recovery_code() for _ in range(count)]
    for code in codes:
        db.session.add(MfaRecoveryCode(user_id=user.id, code_hash=_recovery_code_hash(code)))
    return codes


def _provisioning_payload(user: User, secret: str) -> dict:
    issuer = current_app.config['MFA_TOTP_ISSUER']
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)
    image = qrcode.make(uri, image_factory=SvgPathImage)
    stream = BytesIO()
    image.save(stream)
    qr_data_uri = 'data:image/svg+xml;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')
    return {
        'manual_key': secret,
        'provisioning_uri': uri,
        'qr_code_data_uri': qr_data_uri,
        'issuer': issuer,
    }


def start_mfa_enrollment(challenge_token: str) -> tuple[User, dict]:
    _, user = _load_challenge(challenge_token, 'enroll')
    if user.email_verified_at is None:
        raise MfaError('email_verification_required')
    if user.mfa_enabled_at is not None:
        raise MfaError('mfa_already_enabled')

    secret = pyotp.random_base32()
    user.mfa_pending_secret_encrypted = _encrypt_secret(secret)
    db.session.commit()
    return user, _provisioning_payload(user, secret)


def confirm_mfa_enrollment(challenge_token: str, code: str) -> tuple[User, list[str], dict]:
    payload, user = _load_challenge(challenge_token, 'enroll')
    if user.email_verified_at is None:
        raise MfaError('email_verification_required')

    secret = _decrypt_secret(user.mfa_pending_secret_encrypted)
    matched_timecode = _totp_match(secret, code)
    if matched_timecode is None:
        remaining = _record_challenge_failure(challenge_token, payload)
        raise MfaError('invalid_totp', attempts_remaining=remaining)

    _consume_challenge(challenge_token)
    user.mfa_secret_encrypted = user.mfa_pending_secret_encrypted
    user.mfa_pending_secret_encrypted = None
    user.mfa_enabled_at = utcnow()
    user.mfa_last_used_timecode = matched_timecode
    recovery_codes = generate_recovery_codes(user)
    return user, recovery_codes, payload


def _use_recovery_code(user: User, code: str) -> bool:
    code_hash = _recovery_code_hash(code)
    recovery_code = db.session.execute(
        select(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.user_id == user.id,
            MfaRecoveryCode.code_hash == code_hash,
            MfaRecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not recovery_code:
        return False
    recovery_code.used_at = utcnow()
    return True


def verify_mfa_challenge(challenge_token: str, code: str) -> tuple[User, str, dict]:
    payload, user = _load_challenge(challenge_token, 'verify')
    if user.mfa_enabled_at is None:
        raise MfaError('mfa_not_enabled')

    secret = _decrypt_secret(user.mfa_secret_encrypted)
    matched_timecode = _totp_match(secret, code, user.mfa_last_used_timecode)
    method = 'totp'
    if matched_timecode is not None:
        user.mfa_last_used_timecode = matched_timecode
    elif _use_recovery_code(user, code):
        method = 'recovery_code'
    else:
        remaining = _record_challenge_failure(challenge_token, payload)
        raise MfaError('invalid_mfa_code', attempts_remaining=remaining)

    _consume_challenge(challenge_token)
    return user, method, payload


def verify_current_totp(user: User, code: str) -> None:
    if user.mfa_enabled_at is None:
        raise MfaError('mfa_not_enabled')
    secret = _decrypt_secret(user.mfa_secret_encrypted)
    matched_timecode = _totp_match(secret, code, user.mfa_last_used_timecode)
    if matched_timecode is None:
        raise MfaError('invalid_totp')
    user.mfa_last_used_timecode = matched_timecode


def recovery_codes_remaining(user: User) -> int:
    return MfaRecoveryCode.query.filter_by(user_id=user.id, used_at=None).count()


def mfa_status(user: User) -> dict:
    return {
        'enabled': user.mfa_enabled_at is not None,
        'enabled_at': user.mfa_enabled_at.isoformat() if user.mfa_enabled_at else None,
        'required': is_mfa_required(user),
        'email_verified': user.email_verified_at is not None,
        'recovery_codes_remaining': recovery_codes_remaining(user) if user.mfa_enabled_at else 0,
    }


def password_is_valid(user: User, password: str) -> bool:
    return verify_password(password, user.password_hash)
