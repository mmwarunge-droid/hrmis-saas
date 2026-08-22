from sqlalchemy import inspect as sa_inspect

from app.extensions import db
from app.models import AuthSession, Employee, Tenant, User
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
        'invited': 0,
    }



def test_super_admin_user_directory_spans_filters_and_manages_tenants(
    app,
    tenant,
):
    with app.app_context():
        register_user({
            'email': 'platform-directory-admin@example.test',
            'first_name': 'Platform',
            'last_name': 'Directory Admin',
            'password': 'StrongPlatformDirectoryPass123!',
            'roles': ['SUPER_ADMIN'],
        })

        other = Tenant(
            name='Platform Directory Other Tenant',
            slug='platform-directory-other-tenant',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    _create_user(
        app,
        tenant.id,
        701,
        roles=['EMPLOYEE'],
    )
    other_user_id = _create_user(
        app,
        other_id,
        702,
        roles=['EMPLOYEE'],
    )

    platform_client = app.test_client()
    login = platform_client.post(
        '/api/auth/login',
        json={
            'email': 'platform-directory-admin@example.test',
            'password': 'StrongPlatformDirectoryPass123!',
        },
    )
    assert login.status_code == 200
    headers = _csrf_header(platform_client)

    # No tenant_id means complete platform scope for SUPER_ADMIN.
    response = platform_client.get(
        '/api/users?per_page=100',
        headers=headers,
    )
    assert response.status_code == 200

    data = response.get_json()['data']
    emails = {item['email'] for item in data['items']}

    assert 'user-701@acme.test' in emails
    assert 'user-702@acme.test' in emails

    # An explicit organization filter must narrow the platform scope.
    filtered = platform_client.get(
        f'/api/users?tenant_id={other_id}&per_page=100',
        headers=headers,
    )
    assert filtered.status_code == 200

    filtered_data = filtered.get_json()['data']
    assert filtered_data['meta']['total'] == 1
    assert {
        item['email']
        for item in filtered_data['items']
    } == {'user-702@acme.test'}

    summary = platform_client.get(
        f'/api/users/summary?tenant_id={other_id}',
        headers=headers,
    )
    assert summary.status_code == 200
    assert summary.get_json()['data']['total'] == 1

    # SUPER_ADMIN can issue a secure reset email for a user in
    # another organization without receiving the raw token.
    shared = platform_client.post(
        f'/api/users/{other_user_id}/access-link/share',
        headers=headers,
    )
    assert shared.status_code == 200

    shared_data = shared.get_json()['data']
    assert shared_data['user']['email'] == 'user-702@acme.test'
    assert shared_data['link_type'] == 'password_reset'
    assert shared_data['delivery'] == 'sent'
    assert 'token' not in shared_data
    assert 'url' not in shared_data

    message = app.extensions['mail_outbox'][-1]
    assert message['subject'] == 'Reset your Kinetic password'


def test_client_admin_cannot_share_access_link_across_tenants(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        other = Tenant(
            name='Protected Other Tenant',
            slug='protected-other-tenant-access-link',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    other_user_id = _create_user(
        app,
        other_id,
        703,
        roles=['EMPLOYEE'],
    )

    response = client.post(
        f'/api/users/{other_user_id}/access-link/share',
        headers=auth_headers,
    )

    # Tenant-scoped administrators must not be able to resolve
    # or operate on another organization's account.
    assert response.status_code == 404



def test_super_admin_can_send_bulk_password_resets_by_selection(
    app,
    tenant,
):
    with app.app_context():
        register_user({
            'email': 'bulk-reset-platform-admin@example.test',
            'first_name': 'Bulk',
            'last_name': 'Platform Admin',
            'password': 'StrongBulkPlatformPass123!',
            'roles': ['SUPER_ADMIN'],
        })

        other = Tenant(
            name='Bulk Reset Other Tenant',
            slug='bulk-reset-other-tenant',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    with app.app_context():
        platform_target = register_user({
            'email': 'bulk-reset-protected-platform@example.test',
            'first_name': 'Protected',
            'last_name': 'Platform Account',
            'password': 'StrongProtectedPlatformPass123!',
            'roles': ['SUPER_ADMIN'],
        })
        platform_target_id = platform_target.id

    first_id = _create_user(
        app,
        tenant.id,
        711,
        roles=['EMPLOYEE'],
    )
    second_id = _create_user(
        app,
        other_id,
        712,
        roles=['EMPLOYEE'],
    )
    inactive_id = _create_user(
        app,
        other_id,
        713,
        roles=['EMPLOYEE'],
        is_active=False,
    )

    platform_client = app.test_client()
    login = platform_client.post(
        '/api/auth/login',
        json={
            'email': 'bulk-reset-platform-admin@example.test',
            'password': 'StrongBulkPlatformPass123!',
        },
    )
    assert login.status_code == 200
    headers = _csrf_header(platform_client)

    before_mail = len(app.extensions.get('mail_outbox', []))

    response = platform_client.post(
        '/api/users/password-reset/share-bulk',
        headers=headers,
        json={
            'user_ids': [
                str(first_id),
                str(second_id),
                str(inactive_id),
                str(platform_target_id),
            ],
        },
    )

    assert response.status_code == 200
    data = response.get_json()['data']

    assert data['scope'] == 'selected'
    assert data['requested'] == 4
    assert data['sent'] == 2
    assert data['skipped'] == 2
    assert data['failed'] == 0
    assert data['skipped_reasons']['inactive'] == 1
    assert data['skipped_reasons']['awaiting_activation'] == 0
    assert data['skipped_reasons']['platform_account'] == 1

    assert len(app.extensions['mail_outbox']) == before_mail + 2
    assert all(
        message['subject'] == 'Reset your Kinetic password'
        for message in app.extensions['mail_outbox'][-2:]
    )


def test_super_admin_can_send_bulk_password_resets_by_organization(
    app,
    tenant,
):
    with app.app_context():
        register_user({
            'email': 'organization-reset-admin@example.test',
            'first_name': 'Organization',
            'last_name': 'Reset Admin',
            'password': 'StrongOrganizationResetPass123!',
            'roles': ['SUPER_ADMIN'],
        })

        other = Tenant(
            name='Organization Reset Tenant',
            slug='organization-reset-tenant',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    _create_user(
        app,
        other_id,
        721,
        roles=['EMPLOYEE'],
    )
    _create_user(
        app,
        other_id,
        722,
        roles=['MANAGER'],
    )
    _create_user(
        app,
        other_id,
        723,
        roles=['EMPLOYEE'],
        is_active=False,
    )

    # A user from another organization must not be included.
    _create_user(
        app,
        tenant.id,
        724,
        roles=['EMPLOYEE'],
    )

    platform_client = app.test_client()
    login = platform_client.post(
        '/api/auth/login',
        json={
            'email': 'organization-reset-admin@example.test',
            'password': 'StrongOrganizationResetPass123!',
        },
    )
    assert login.status_code == 200
    headers = _csrf_header(platform_client)

    before_mail = len(app.extensions.get('mail_outbox', []))

    response = platform_client.post(
        '/api/users/password-reset/share-bulk',
        headers=headers,
        json={'tenant_id': str(other_id)},
    )

    assert response.status_code == 200
    data = response.get_json()['data']

    assert data['scope'] == 'organization'
    assert data['tenant_id'] == str(other_id)
    assert data['requested'] == 3
    assert data['sent'] == 2
    assert data['skipped'] == 1
    assert data['failed'] == 0
    assert data['skipped_reasons']['inactive'] == 1

    assert len(app.extensions['mail_outbox']) == before_mail + 2


def test_client_admin_cannot_send_bulk_password_resets(
    client,
    auth_headers,
):
    response = client.post(
        '/api/users/password-reset/share-bulk',
        headers=auth_headers,
        json={
            'user_ids': [
                '11111111-1111-1111-1111-111111111111',
            ],
        },
    )

    assert response.status_code == 403
    assert response.get_json()['error']['code'] == 'FORBIDDEN'


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
        employee = Employee(
            tenant_id=tenant.id,
            user_id=target.id,
            employee_number='LIFE-001',
            first_name='Lifecycle',
            last_name='User',
            email='lifecycle.profile@acme.test',
            hire_date=utcnow().date(),
            employment_status='active',
        )
        db.session.add(employee)
        db.session.commit()
        employee_id = employee.id

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
        employee = db.session.get(Employee, employee_id)
        assert employee.employment_status == 'inactive'

    blocked = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'lifecycle@acme.test',
            'password': 'StrongLifecyclePass123!',
        },
    )
    assert blocked.status_code == 403
    assert blocked.get_json()['error']['code'] == 'ACCOUNT_INACTIVE'
    assert 'system administrator' in blocked.get_json()['error']['message']

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
            'roles': ['EMPLOYEE'],
        },
    )
    assert platform_employee.status_code == 400
    assert 'SUPER_ADMIN role' in str(
        platform_employee.get_json()['error']['message']
    )
