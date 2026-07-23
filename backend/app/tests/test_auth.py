from app.models import AuthSession


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


def test_logout_all_revokes_every_session(client, app, admin_user):
    assert _login(client).status_code == 200
    other_client = app.test_client()
    assert _login(other_client).status_code == 200

    response = other_client.post('/api/auth/logout-all', headers=_csrf_header(other_client))

    assert response.status_code == 200
    assert response.get_json()['data']['revoked_sessions'] == 2
    assert client.get('/api/auth/me').status_code == 401
    assert other_client.get('/api/auth/me').status_code == 401


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
