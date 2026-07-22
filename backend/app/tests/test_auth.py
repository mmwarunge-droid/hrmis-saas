def test_login_success(client, admin_user):
    res = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    body = res.get_json()
    assert res.status_code == 200
    assert body['success'] is True
    assert 'access_token' in body['data']
    assert 'refresh_token' in body['data']


def test_protected_route_requires_token(client):
    res = client.get('/api/auth/me')
    assert res.status_code == 401
