def test_health_endpoint(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json()['data']['status'] == 'ok'


def test_blueprint_prefixes_preserve_resource_paths(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert '/api/auth/login' in rules
    assert '/api/users' in rules
    assert '/api/employees' in rules
    assert '/api/documents' in rules


def test_public_first_user_bootstrap_is_disabled(client):
    response = client.post(
        '/api/auth/register',
        json={
            'email': 'attacker@example.com',
            'first_name': 'Untrusted',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['SUPER_ADMIN'],
        },
    )

    assert response.status_code == 401
    assert response.get_json()['error']['code'] == 'AUTHENTICATION_REQUIRED'


def test_tenant_admin_cannot_assign_super_admin(client, auth_headers, tenant):
    response = client.post(
        '/api/users',
        headers=auth_headers,
        json={
            'tenant_id': str(tenant.id),
            'email': 'escalation@acme.test',
            'first_name': 'Privilege',
            'last_name': 'Escalation',
            'password': 'StrongPass123!',
            'roles': ['SUPER_ADMIN'],
        },
    )

    assert response.status_code == 400
    assert 'SUPER_ADMIN' in str(response.get_json()['error']['message'])



def test_bootstrap_admin_cli_creates_first_platform_admin(app, monkeypatch):
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL', 'platform@example.com')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'StrongBootstrapPass123!')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_FIRST_NAME', 'Platform')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_LAST_NAME', 'Administrator')

    result = app.test_cli_runner().invoke(args=['bootstrap-admin'])

    assert result.exit_code == 0
    assert 'Created SUPER_ADMIN user platform@example.com' in result.output
