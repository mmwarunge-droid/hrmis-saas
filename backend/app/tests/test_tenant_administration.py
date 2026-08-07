from app.extensions import db
from app.models import AuthSession, Role, Tenant, User, UserRole
from app.services.auth_service import register_user
from app.services.rbac_service import set_user_roles


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _login_super_admin(app):
    with app.app_context():
        register_user({
            'email': 'platform-admin@example.com',
            'first_name': 'Platform',
            'last_name': 'Administrator',
            'password': 'StrongPlatformPass123!',
            'roles': ['SUPER_ADMIN'],
        })
    client = app.test_client()
    response = client.post(
        '/api/auth/login',
        json={
            'email': 'platform-admin@example.com',
            'password': 'StrongPlatformPass123!',
        },
    )
    assert response.status_code == 200
    return client, _csrf_header(client)


def _add_account(app, tenant_id, index, role='EMPLOYEE'):
    with app.app_context():
        user = User(
            tenant_id=tenant_id,
            email=f'org-user-{tenant_id}-{index}@example.test',
            first_name='Organization',
            last_name=f'User {index}',
            password_hash='not-used',
        )
        db.session.add(user)
        db.session.flush()
        set_user_roles(user, [role], commit=False)
        db.session.commit()
        return user.id


def test_organization_directory_has_complete_totals_and_counts(app):
    super_client, headers = _login_super_admin(app)
    tenant_ids = []
    with app.app_context():
        for index in range(1, 36):
            tenant = Tenant(
                name=f'Organization {index:02d}',
                slug=f'organization-{index:02d}',
                country='Kenya' if index % 2 else 'Uganda',
                industry='Technology',
                status='suspended' if index in {34, 35} else 'active',
            )
            db.session.add(tenant)
            db.session.flush()
            tenant_ids.append(tenant.id)
        db.session.commit()

    _add_account(app, tenant_ids[0], 1, role='CLIENT_ADMIN')
    _add_account(app, tenant_ids[0], 2)
    _add_account(app, tenant_ids[1], 3, role='CLIENT_ADMIN')

    response = super_client.get(
        '/api/tenants?page=2&per_page=12&sort=name&direction=asc',
        headers=headers,
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['meta']['total'] == 35
    assert data['meta']['page'] == 2
    assert len(data['items']) == 12

    first_page = super_client.get(
        '/api/tenants?page=1&per_page=12&sort=people&direction=desc',
        headers=headers,
    ).get_json()['data']
    assert first_page['items'][0]['user_count'] == 2
    assert first_page['items'][0]['admin_count'] == 1
    assert first_page['items'][0]['primary_admin']['email'].startswith(
        'org-user-'
    )

    suspended = super_client.get(
        '/api/tenants?status=suspended',
        headers=headers,
    ).get_json()['data']
    assert suspended['meta']['total'] == 2

    search = super_client.get(
        '/api/tenants?q=organization%2035',
        headers=headers,
    ).get_json()['data']
    assert search['meta']['total'] == 1

    summary = super_client.get(
        '/api/tenants/summary',
        headers=headers,
    ).get_json()['data']
    assert summary == {
        'total': 35,
        'active': 33,
        'suspended': 2,
        'archived': 0,
        'users': 3,
        'admins': 2,
    }

    options = super_client.get(
        '/api/tenants/options',
        headers=headers,
    ).get_json()['data']['items']
    assert len(options) == 35


def test_tenant_read_access_is_limited_to_actor_organization(app):
    with app.app_context():
        own = Tenant(name='Owner Tenant', slug='owner-tenant')
        other = Tenant(name='Hidden Tenant', slug='hidden-tenant')
        db.session.add_all([own, other])
        db.session.flush()
        owner = register_user({
            'tenant_id': own.id,
            'email': 'owner@example.test',
            'first_name': 'Organization',
            'last_name': 'Owner',
            'password': 'StrongOwnerPass123!',
            'roles': ['ORGANIZATION_OWNER'],
        })
        own_id = own.id
        other_id = other.id
        owner_id = owner.id

    client = app.test_client()
    response = client.post(
        '/api/auth/login',
        json={
            'email': 'owner@example.test',
            'password': 'StrongOwnerPass123!',
        },
    )
    assert response.status_code == 200

    listed = client.get('/api/tenants').get_json()['data']
    assert listed['meta']['total'] == 1
    assert listed['items'][0]['id'] == str(own_id)

    assert client.get(f'/api/tenants/{own_id}').status_code == 200
    assert client.get(f'/api/tenants/{other_id}').status_code == 404

    with app.app_context():
        role = Role.query.filter_by(name='ORGANIZATION_OWNER').one()
        link = UserRole.query.filter_by(
            user_id=owner_id,
            role_id=role.id,
        ).one()
        assert str(link.tenant_id) == str(own_id)


def test_suspending_organization_revokes_sessions_and_blocks_login(app):
    super_client, headers = _login_super_admin(app)
    with app.app_context():
        tenant = Tenant(
            name='Lifecycle Tenant',
            slug='lifecycle-tenant',
        )
        db.session.add(tenant)
        db.session.flush()
        tenant_id = tenant.id
        admin = register_user({
            'tenant_id': tenant.id,
            'email': 'tenant-admin@example.test',
            'first_name': 'Tenant',
            'last_name': 'Administrator',
            'password': 'StrongTenantAdminPass123!',
            'roles': ['CLIENT_ADMIN'],
        })
        admin_id = admin.id

    tenant_client = app.test_client()
    login = tenant_client.post(
        '/api/auth/login',
        json={
            'email': 'tenant-admin@example.test',
            'password': 'StrongTenantAdminPass123!',
        },
    )
    assert login.status_code == 200

    suspended = super_client.patch(
        f'/api/tenants/{tenant_id}',
        headers=headers,
        json={'status': 'suspended'},
    )
    assert suspended.status_code == 200
    assert suspended.get_json()['data']['status'] == 'suspended'
    assert suspended.get_json()['data']['revoked_sessions'] == 1

    with app.app_context():
        session = AuthSession.query.filter_by(user_id=admin_id).one()
        assert session.revoked_at is not None
        assert session.revoked_reason == 'organization_suspended'

    blocked = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'tenant-admin@example.test',
            'password': 'StrongTenantAdminPass123!',
        },
    )
    assert blocked.status_code == 401

    reactivated = super_client.patch(
        f'/api/tenants/{tenant_id}',
        headers=headers,
        json={'status': 'active'},
    )
    assert reactivated.status_code == 200

    allowed = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'tenant-admin@example.test',
            'password': 'StrongTenantAdminPass123!',
        },
    )
    assert allowed.status_code == 200
