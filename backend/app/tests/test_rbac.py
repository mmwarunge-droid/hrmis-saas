def test_rbac_blocks_missing_permission(client, app, tenant):
    from app.services.auth_service import register_user
    with app.app_context():
        register_user({'tenant_id': tenant.id, 'email': 'employee@acme.test', 'first_name': 'Emp', 'last_name': 'One', 'password': 'StrongPass123!', 'roles': ['EMPLOYEE']})
    token = client.post('/api/auth/login', json={'email': 'employee@acme.test', 'password': 'StrongPass123!'}).get_json()['data']['access_token']
    res = client.post('/api/users', headers={'Authorization': f'Bearer {token}'}, json={'email': 'x@y.test', 'first_name': 'X', 'last_name': 'Y', 'password': 'StrongPass123!', 'roles': ['EMPLOYEE']})
    assert res.status_code == 403
