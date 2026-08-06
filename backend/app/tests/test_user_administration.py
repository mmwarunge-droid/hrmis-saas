from sqlalchemy import inspect as sa_inspect

from app.extensions import db
from app.models import AuthSession, Tenant, User
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.rbac_service import set_user_roles


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _create_user(
    app,
    tenant_id,
    index,
    *,
    roles=None,
    is_active=True,
    verified=False,
):
    with app.app_context():
        user = User(
            tenant_id=tenant_id,
            email=f'user-{index:03d}@acme.test',
            first_name='Member',
            last_name=f'{index:03d}',
            password_hash='not-used',
            is_active=is_active,
            email_verified_at=utcnow() if verified else None,
        )
        db.session.add(user)
        db.session.flush()
        set_user_roles(
            user,
            roles or ['EMPLOYEE'],
            commit=False,
        )
        db.session.commit()
        return user.id


def test_user_directory_uses_complete_scope_and_server_controls(
    client,
    app,
    tenant,
    auth_headers,
):
    for index in range(1, 35):
        _create_user(
            app,
            tenant.id,
            index,
            roles=['MANAGER'] if index <= 4 else ['EMPLOYEE'],
            is_active=index != 34,
            verified=index <= 20,
        )

    with app.app_context():
        other = Tenant(
            name='Other Tenant',
            slug='other-tenant-users',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    for index in range(101, 107):
        _create_user(app, other_id, index)

    response = client.get(
        '/api/users?page=2&per_page=15&sort=full_name&direction=asc',
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['meta']['total'] == 35
    assert data['meta']['page'] == 2
    assert len(data['items']) == 15
    assert all(
        item['tenant_id'] == str(tenant.id)
        for item in data['items']
    )

    managers = client.get(
        '/api/users?role=MANAGER&per_page=15',
        headers=auth_headers,
    ).get_json()['data']
    assert managers['meta']['total'] == 4
    assert all('MANAGER' in item['roles'] for item in managers['items'])

    inactive = client.get(
        '/api/users?status=inactive',
        headers=auth_headers,
    ).get_json()['data']
    assert inactive['meta']['total'] == 1

    search = client.get(
        '/api/users?q=member%20034',
        headers=auth_headers,
    ).get_json()['data']
    assert search['meta']['total'] == 1
    assert search['items'][0]['email'] == 'user-034@acme.test'

    summary = client.get(
        '/api/users/summary',
        headers=auth_headers,
    ).get_json()['data']
    assert summary == {
        'total': 35,
        'active': 34,
        'verified': 20,
        'mfa_enabled': 0,
        'privileged': 1,
    }


def test_deactivating_user_revokes_sessions_and_blocks_login(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        target = register_user({
            'tenant_id': tenant.id,
            'email': 'lifecycle@acme.test',
            'first_name': 'Lifecycle',
            'last_name': 'User',
            'password': 'StrongLifecyclePass123!',
            'roles': ['EMPLOYEE'],
        })
        target_id = target.id

    employee_client = app.test_client()
    login = employee_client.post(
        '/api/auth/login',
        json={
            'email': 'lifecycle@acme.test',
            'password': 'StrongLifecyclePass123!',
        },
    )
    assert login.status_code == 200

    admin_client = app.test_client()
    admin_login = admin_client.post(
        '/api/auth/login',
        json={
            'email': 'admin@acme.test',
            'password': 'StrongPass123!',
        },
    )
    assert admin_login.status_code == 200

    response = admin_client.patch(
        f'/api/users/{target_id}',
        headers=_csrf_header(admin_client),
        json={'is_active': False},
    )
    assert response.status_code == 200
    assert response.get_json()['data']['is_active'] is False
    assert response.get_json()['data']['revoked_sessions'] == 1

    with app.app_context():
        session = AuthSession.query.filter_by(user_id=target_id).one()
        assert session.revoked_at is not None
        assert session.revoked_reason == 'account_deactivated_by_administrator'

    blocked = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'lifecycle@acme.test',
            'password': 'StrongLifecyclePass123!',
        },
    )
    assert blocked.status_code == 401

    with app.app_context():
        admin_id = sa_inspect(admin_user).identity[0]
    self_deactivate = admin_client.patch(
        f'/api/users/{admin_id}',
        headers=_csrf_header(admin_client),
        json={'is_active': False},
    )
    assert self_deactivate.status_code == 409
    assert self_deactivate.get_json()['error']['code'] == (
        'SELF_DEACTIVATION_NOT_ALLOWED'
    )


def test_platform_role_assignments_respect_account_scope(app, tenant):
    with app.app_context():
        register_user({
            'email': 'platform-role-admin@example.test',
            'first_name': 'Platform',
            'last_name': 'Role Admin',
            'password': 'StrongPlatformRolePass123!',
            'roles': ['SUPER_ADMIN'],
        })

    client = app.test_client()
    login = client.post(
        '/api/auth/login',
        json={
            'email': 'platform-role-admin@example.test',
            'password': 'StrongPlatformRolePass123!',
        },
    )
    assert login.status_code == 200
    headers = _csrf_header(client)

    tenant_super_admin = client.post(
        '/api/users',
        headers=headers,
        json={
            'tenant_id': str(tenant.id),
            'email': 'tenant-super-admin@example.test',
            'first_name': 'Tenant',
            'last_name': 'Super Admin',
            'password': 'StrongTenantSuperPass123!',
            'roles': ['SUPER_ADMIN'],
        },
    )
    assert tenant_super_admin.status_code == 400
    assert 'platform accounts' in str(
        tenant_super_admin.get_json()['error']['message']
    )

    platform_employee = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'platform-employee@example.test',
            'first_name': 'Platform',
            'last_name': 'Employee',
            'password': 'StrongPlatformEmployeePass123!',
            'roles': ['EMPLOYEE'],
        },
    )
    assert platform_employee.status_code == 400
    assert 'SUPER_ADMIN role' in str(
        platform_employee.get_json()['error']['message']
    )
