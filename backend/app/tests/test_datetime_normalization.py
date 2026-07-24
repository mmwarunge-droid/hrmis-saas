from datetime import datetime, timedelta, timezone

from app.models.account_token import AccountToken
from app.models.auth_session import AuthSession
from app.models.base import to_utc_naive
from app.services.session_service import _ttl_seconds


def test_to_utc_naive_converts_aware_datetime():
    aware = datetime(
        2026,
        7,
        24,
        3,
        0,
        tzinfo=timezone.utc,
    )

    normalized = to_utc_naive(aware)

    assert normalized == datetime(2026, 7, 24, 3, 0)
    assert normalized.tzinfo is None


def test_to_utc_naive_preserves_naive_datetime():
    naive = datetime(2026, 7, 24, 3, 0)

    assert to_utc_naive(naive) is naive


def test_session_expiry_accepts_aware_datetime():
    auth_session = AuthSession(
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=5),
    )

    assert auth_session.is_active is True
    assert _ttl_seconds(auth_session.expires_at) > 0


def test_account_token_expiry_accepts_aware_datetime():
    account_token = AccountToken(
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=5),
    )

    assert account_token.active is True
