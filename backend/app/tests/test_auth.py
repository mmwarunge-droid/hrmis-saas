from app.models import AuditLog, AuthSession


def _set_cookie_headers(response):
    return response.headers.getlist('Set-Cookie')


def _login(client):
    return client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})


def _csrf_header(client, cookie_name='csrf_access_token'):
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def test_login_sets_http_only_jwt_cookies_and_returns_no_tokens(client, admin_user):
    response = _login(client)
    body = response.get_json()
    cookies = _set_cookie_headers(response)

    assert response.status_code == 200
    assert body['success'] is True
    assert body['data']['user']['email'] == 'admin@acme.test'
    assert 'access_token' not in body['data']
    assert 'refresh_token' not in body['data']
    assert any(cookie.startswith('access_token_cookie=') and 'HttpOnly' in cookie for cookie in cookies)
    assert any(cookie.startswith('refresh_token_cookie=') and 'HttpOnly' in cookie for cookie in cookies)
    assert any(cookie.startswith('csrf_access_token=') and 'HttpOnly' not in cookie for cookie in cookies)
    assert any(cookie.startswith('csrf_refresh_token=') and 'HttpOnly' not in cookie for cookie in cookies)


def test_protected_route_requires_cookie(client):
    response = client.get('/api/auth/me')

    assert response.status_code == 401


def test_cookie_authentication_loads_current_user(client, admin_user):
    login = _login(client)
    assert login.status_code == 200

    response = client.get('/api/auth/me')

    assert response.status_code == 200
    assert response.get_json()['data']['email'] == 'admin@acme.test'


def test_state_changing_request_requires_csrf_header(client, admin_user):
    login = _login(client)
    assert login.status_code == 200

    response = client.post('/api/auth/logout')

    assert response.status_code == 401
    assert response.get_json()['error']['code'] == 'AUTHENTICATION_REQUIRED'


def test_refresh_rotates_refresh_cookie_and_csrf_value(client, admin_user):
    login = _login(client)
    assert login.status_code == 200
    old_refresh = client.get_cookie('refresh_token_cookie', path='/api/auth/refresh')
    old_csrf = client.get_cookie('csrf_refresh_token')
    assert old_refresh is not None
    assert old_csrf is not None

    response = client.post(
        '/api/auth/refresh',
        headers={'X-CSRF-TOKEN': old_csrf.value},
    )

    assert response.status_code == 200
    assert 'access_token' not in response.get_json()['data']
    assert client.get_cookie('refresh_token_cookie', path='/api/auth/refresh').value != old_refresh.value
    assert client.get_cookie('csrf_refresh_token').value != old_csrf.value
    cookies = _set_cookie_headers(response)
    assert any(cookie.startswith('access_token_cookie=') for cookie in cookies)
    assert any(cookie.startswith('refresh_token_cookie=') for cookie in cookies)


def test_refresh_token_reuse_revokes_the_session(client, app, admin_user):
    login = _login(client)
    assert login.status_code == 200
    old_refresh = client.get_cookie('refresh_token_cookie', path='/api/auth/refresh')
    old_csrf = client.get_cookie('csrf_refresh_token')
    assert old_refresh is not None
    assert old_csrf is not None

    first_refresh = client.post(
        '/api/auth/refresh',
        headers={'X-CSRF-TOKEN': old_csrf.value},
    )
    assert first_refresh.status_code == 200

    client.set_cookie('refresh_token_cookie', old_refresh.value, path='/api/auth/refresh')
    client.set_cookie('csrf_refresh_token', old_csrf.value, path='/')
    replay = client.post(
        '/api/auth/refresh',
        headers={'X-CSRF-TOKEN': old_csrf.value},
    )

    assert replay.status_code == 401
    assert replay.get_json()['error']['code'] == 'REFRESH_TOKEN_REUSED'
    with app.app_context():
        auth_session = AuthSession.query.one()
        assert auth_session.revoked_at is not None
        assert auth_session.revoked_reason == 'refresh_token_reuse'
        assert AuditLog.query.filter_by(action='auth.refresh_token_reuse').count() == 1


def test_session_listing_marks_current_session(client, admin_user):
    login = _login(client)
    assert login.status_code == 200

    response = client.get('/api/auth/sessions')

    assert response.status_code == 200
    sessions = response.get_json()['data']
    assert len(sessions) == 1
    assert sessions[0]['current'] is True
    assert sessions[0]['active'] is True
    assert 'refresh_jti_hash' not in sessions[0]


def test_user_can_revoke_another_session(client, app, admin_user):
    first_login = _login(client)
    assert first_login.status_code == 200

    other_client = app.test_client()
    second_login = _login(other_client)
    assert second_login.status_code == 200

    sessions_response = other_client.get('/api/auth/sessions')
    sessions = sessions_response.get_json()['data']
    other_session = next(session for session in sessions if not session['current'])

    revoke = other_client.delete(
        f"/api/auth/sessions/{other_session['id']}",
        headers=_csrf_header(other_client),
    )

    assert revoke.status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    assert other_client.get('/api/auth/me').status_code == 200
    with app.app_context():
        assert AuditLog.query.filter_by(action='auth.session_revoked').count() == 1


def test_logout_all_revokes_every_session(client, app, admin_user):
    assert _login(client).status_code == 200
    other_client = app.test_client()
    assert _login(other_client).status_code == 200

    response = other_client.post('/api/auth/logout-all', headers=_csrf_header(other_client))

    assert response.status_code == 200
    assert response.get_json()['data']['revoked_sessions'] == 2
    assert client.get('/api/auth/me').status_code == 401
    assert other_client.get('/api/auth/me').status_code == 401
    with app.app_context():
        assert AuditLog.query.filter_by(action='auth.logout_all').count() == 1


def test_logout_clears_authentication_cookies_and_revokes_session(client, app, admin_user):
    login = _login(client)
    assert login.status_code == 200

    response = client.post('/api/auth/logout', headers=_csrf_header(client))

    assert response.status_code == 200
    cookies = _set_cookie_headers(response)
    assert any(cookie.startswith('access_token_cookie=;') for cookie in cookies)
    assert any(cookie.startswith('refresh_token_cookie=;') for cookie in cookies)
    with app.app_context():
        auth_session = AuthSession.query.one()
        assert auth_session.revoked_at is not None
        assert auth_session.revoked_reason == 'user_logout'
        assert AuditLog.query.filter_by(action='auth.logout').count() == 1


def test_failed_logins_lock_account_with_enumeration_safe_response(client, app, admin_user):
    from app.models import AuditLog, User

    app.config.update(
        AUTH_MAX_FAILED_ATTEMPTS=3,
        AUTH_FAILURE_WINDOW_MINUTES=15,
        AUTH_LOCKOUT_MINUTES=10,
    )

    known_responses = [
        client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'WrongPass123!'})
        for _ in range(3)
    ]
    unknown = client.post(
        '/api/auth/login',
        json={'email': 'missing@acme.test', 'password': 'WrongPass123!'},
    )
    locked = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )

    expected_error = {
        'code': 'INVALID_CREDENTIALS',
        'message': 'Invalid email or password',
    }
    for response in [*known_responses, unknown, locked]:
        assert response.status_code == 401
        assert response.get_json()['error'] == expected_error

    with app.app_context():
        user = User.query.filter_by(email='admin@acme.test').one()
        assert user.failed_login_attempts == 3
        assert user.locked_until is not None
        assert AuditLog.query.filter_by(action='auth.login_failed').count() == 5
        assert AuditLog.query.filter_by(action='auth.account_locked').count() == 1


def test_successful_login_after_lock_expiry_resets_failure_state(client, app, admin_user):
    from datetime import timedelta

    from app.extensions import db
    from app.models import User
    from app.models.base import utcnow

    with app.app_context():
        user = User.query.filter_by(email='admin@acme.test').one()
        user.failed_login_attempts = 5
        user.last_failed_login_at = utcnow() - timedelta(minutes=20)
        user.locked_until = utcnow() - timedelta(seconds=1)
        db.session.commit()

    response = _login(client)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='admin@acme.test').one()
        assert user.failed_login_attempts == 0
        assert user.last_failed_login_at is None
        assert user.locked_until is None


def test_auth_audit_metadata_is_privacy_safe(client, app, admin_user):
    from app.models import AuditLog

    response = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'WrongPass123!'},
        headers={'User-Agent': 'curl/8.5.0 secret-fingerprint'},
        environ_base={'REMOTE_ADDR': '203.0.113.44'},
    )

    assert response.status_code == 401
    with app.app_context():
        event = AuditLog.query.filter_by(action='auth.login_failed').one()
        assert event.ip_address == '203.0.113.0/24'
        assert event.user_agent.startswith('curl:')
        assert '203.0.113.44' not in event.user_agent
        assert 'secret-fingerprint' not in event.user_agent
        fingerprint = event.metadata_json['identifier_fingerprint']
        assert len(fingerprint) == 24
        assert 'admin@acme.test' not in str(event.metadata_json)


def test_new_network_and_user_agent_generate_suspicious_login_event(client, app, admin_user):
    from app.models import AuditLog

    first = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
        headers={'User-Agent': 'Mozilla/5.0 Chrome/126.0'},
        environ_base={'REMOTE_ADDR': '192.0.2.10'},
    )
    assert first.status_code == 200

    other_client = app.test_client()
    second = other_client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
        headers={'User-Agent': 'curl/8.5.0'},
        environ_base={'REMOTE_ADDR': '198.51.100.20'},
    )
    assert second.status_code == 200

    with app.app_context():
        event = AuditLog.query.filter_by(action='auth.suspicious_login').one()
        assert set(event.metadata_json['risk_flags']) == {'new_network', 'new_user_agent'}
        assert event.ip_address == '198.51.100.0/24'
        assert event.user_agent.startswith('curl:')


def _token_from_latest_email(app):
    from urllib.parse import parse_qs, urlparse

    message = app.extensions['mail_outbox'][-1]
    link = next(line for line in message['text'].splitlines() if line.startswith('https://'))
    return parse_qs(urlparse(link).fragment)['token'][0]


def test_password_reset_request_is_enumeration_safe_and_stores_only_token_hash(client, app, admin_user):
    import hashlib

    from app.models import AccountToken, AuditLog

    known = client.post('/api/auth/password/forgot', json={'email': 'admin@acme.test'})
    unknown = client.post('/api/auth/password/forgot', json={'email': 'missing@acme.test'})

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.get_json() == unknown.get_json()
    assert len(app.extensions['mail_outbox']) == 1

    raw_token = _token_from_latest_email(app)
    with app.app_context():
        account_token = AccountToken.query.one()
        assert account_token.purpose == AccountToken.PURPOSE_PASSWORD_RESET
        assert account_token.token_hash == hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        assert raw_token not in account_token.token_hash
        assert account_token.consumed_at is None
        assert AuditLog.query.filter_by(action='auth.password_reset_requested').count() == 2


def test_password_reset_is_single_use_and_revokes_existing_sessions(client, app, admin_user):
    from app.models import AccountToken, AuditLog, AuthSession, User
    from app.utils.security import verify_password

    assert _login(client).status_code == 200
    request_response = client.post('/api/auth/password/forgot', json={'email': 'admin@acme.test'})
    assert request_response.status_code == 202
    raw_token = _token_from_latest_email(app)

    reset = client.post(
        '/api/auth/password/reset',
        json={'token': raw_token, 'password': 'DifferentStrongPass456!'},
    )

    assert reset.status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    with app.app_context():
        user = User.query.filter_by(email='admin@acme.test').one()
        account_token = AccountToken.query.one()
        auth_session = AuthSession.query.one()
        assert verify_password('DifferentStrongPass456!', user.password_hash)
        assert account_token.consumed_at is not None
        assert auth_session.revoked_at is not None
        assert auth_session.revoked_reason == 'password_reset'
        assert AuditLog.query.filter_by(action='auth.password_reset_completed').count() == 1

    replay = client.post(
        '/api/auth/password/reset',
        json={'token': raw_token, 'password': 'AnotherStrongPass789!'},
    )
    assert replay.status_code == 400
    assert replay.get_json()['error']['code'] == 'INVALID_OR_EXPIRED_TOKEN'

    old_password = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    new_password = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'DifferentStrongPass456!'},
    )
    assert old_password.status_code == 401
    assert new_password.status_code == 200


def test_email_verification_request_and_confirmation_are_single_use(client, app, admin_user):
    from app.models import AccountToken, AuditLog, User

    assert _login(client).status_code == 200
    request_response = client.post(
        '/api/auth/email-verification/request',
        headers=_csrf_header(client),
    )
    assert request_response.status_code == 202
    raw_token = _token_from_latest_email(app)

    confirmation = client.post(
        '/api/auth/email-verification/confirm',
        json={'token': raw_token},
    )
    assert confirmation.status_code == 200
    assert confirmation.get_json()['data']['email_verified'] is True

    with app.app_context():
        user = User.query.filter_by(email='admin@acme.test').one()
        account_token = AccountToken.query.one()
        assert user.email_verified_at is not None
        assert account_token.consumed_at is not None
        assert AuditLog.query.filter_by(action='auth.email_verified').count() == 1

    me = client.get('/api/auth/me')
    assert me.status_code == 200
    assert me.get_json()['data']['email_verified'] is True

    replay = client.post('/api/auth/email-verification/confirm', json={'token': raw_token})
    assert replay.status_code == 400
    assert replay.get_json()['error']['code'] == 'INVALID_OR_EXPIRED_TOKEN'


def test_expired_password_reset_token_is_rejected(client, app, admin_user):
    from datetime import timedelta

    from app.extensions import db
    from app.models import AccountToken
    from app.models.base import utcnow

    assert client.post('/api/auth/password/forgot', json={'email': 'admin@acme.test'}).status_code == 202
    raw_token = _token_from_latest_email(app)
    with app.app_context():
        account_token = AccountToken.query.one()
        account_token.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()

    response = client.post(
        '/api/auth/password/reset',
        json={'token': raw_token, 'password': 'DifferentStrongPass456!'},
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'INVALID_OR_EXPIRED_TOKEN'
