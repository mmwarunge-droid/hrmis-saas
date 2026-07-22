def test_rbac_blocks_missing_permission(client, app, tenant):
    from app.services.auth_service import register_user

    with app.app_context():
        register_user({
            'tenant_id': tenant.id,
            'email': 'employee@acme.test',
            'first_name': 'Emp',
            'last_name': 'One',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

    login = client.post('/api/auth/login', json={'email': 'employee@acme.test', 'password': 'StrongPass123!'})
    csrf_cookie = client.get_cookie('csrf_access_token')
    assert login.status_code == 200
    assert csrf_cookie is not None

    response = client.post(
        '/api/users',
        headers={'X-CSRF-TOKEN': csrf_cookie.value},
        json={
            'email': 'x@y.test',
            'first_name': 'X',
            'last_name': 'Y',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        },
    )

    assert response.status_code == 403
