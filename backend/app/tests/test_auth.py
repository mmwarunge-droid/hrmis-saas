def _set_cookie_headers(response):
    return response.headers.getlist('Set-Cookie')


def test_login_sets_http_only_jwt_cookies_and_returns_no_tokens(client, admin_user):
    response = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
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
    login = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    assert login.status_code == 200

    response = client.get('/api/auth/me')

    assert response.status_code == 200
    assert response.get_json()['data']['email'] == 'admin@acme.test'


def test_state_changing_request_requires_csrf_header(client, admin_user):
    login = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    assert login.status_code == 200

    response = client.post('/api/auth/logout')

    assert response.status_code == 401
    assert response.get_json()['error']['code'] == 'AUTHENTICATION_REQUIRED'


def test_refresh_uses_refresh_cookie_and_csrf_header(client, admin_user):
    login = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    assert login.status_code == 200
    csrf_cookie = client.get_cookie('csrf_refresh_token')
    assert csrf_cookie is not None

    response = client.post(
        '/api/auth/refresh',
        headers={'X-CSRF-TOKEN': csrf_cookie.value},
    )

    assert response.status_code == 200
    assert 'access_token' not in response.get_json()['data']
    assert any(cookie.startswith('access_token_cookie=') for cookie in _set_cookie_headers(response))


def test_logout_clears_authentication_cookies(client, admin_user):
    login = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    assert login.status_code == 200
    csrf_cookie = client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None

    response = client.post(
        '/api/auth/logout',
        headers={'X-CSRF-TOKEN': csrf_cookie.value},
    )

    assert response.status_code == 200
    cookies = _set_cookie_headers(response)
    assert any(cookie.startswith('access_token_cookie=;') for cookie in cookies)
    assert any(cookie.startswith('refresh_token_cookie=;') for cookie in cookies)
