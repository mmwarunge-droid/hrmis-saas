from app.extensions import db
from app.models import AuditLog, Employee, Tenant, User
from app.services.auth_service import register_user


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _login_super_admin(client, app):
    with app.app_context():
        register_user({
            'email': 'platform@example.com',
            'first_name': 'Platform',
            'last_name': 'Admin',
            'password': 'StrongPlatformPass123!',
            'roles': ['SUPER_ADMIN'],
        })

    response = client.post(
        '/api/auth/login',
        json={'email': 'platform@example.com', 'password': 'StrongPlatformPass123!'},
    )
    assert response.status_code == 200
    return _csrf_header(client)


def test_super_admin_provisions_organization_and_client_admin(client, app):
    headers = _login_super_admin(client, app)

    response = client.post(
        '/api/tenants/provision',
        headers=headers,
        json={
            'organization': {
                'name': 'Northstar Logistics',
                'slug': 'northstar-logistics',
                'legal_name': 'Northstar Logistics Limited',
                'country': 'Kenya',
                'industry': 'Logistics',
                'compliance_region': 'East Africa',
            },
            'admin': {
                'email': 'admin@northstar.test',
                'first_name': 'Amina',
                'last_name': 'Otieno',
            },
        },
    )

    assert response.status_code == 201
    body = response.get_json()['data']
    assert body['organization']['slug'] == 'northstar-logistics'
    assert body['admin']['roles'] == ['CLIENT_ADMIN']
    assert body['admin']['tenant_id'] == body['organization']['id']
    assert body['admin']['account_status'] == 'invited'
    assert body['invitation']['delivery'] == 'sent'

    with app.app_context():
        tenant = Tenant.query.filter_by(slug='northstar-logistics').one()
        admin = User.query.filter_by(email='admin@northstar.test').one()
        assert admin.tenant_id == tenant.id
        assert admin.email_verified_at is None
        assert admin.activation_required is True
        assert admin.invitation_sent_at is not None
        assert AuditLog.query.filter_by(action='tenant.admin_provisioned').count() == 1


def test_client_admin_creates_employee_account_and_profile(client, app, tenant, admin_user):
    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/users',
        headers=_csrf_header(client),
        json={
            'email': 'jane@acme.test',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'roles': ['EMPLOYEE'],
            'employee_profile': {
                'employee_number': 'EMP-001',
                'hire_date': '2026-07-24',
                'job_title': 'People Operations Analyst',
                'employment_type': 'full_time',
                'work_location': 'Nairobi',
            },
        },
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['roles'] == ['EMPLOYEE']
    assert data['account_status'] == 'invited'
    assert data['invitation']['delivery'] == 'sent'
    assert data['employee_profile']['employee_number'] == 'EMP-001'

    with app.app_context():
        user = User.query.filter_by(email='jane@acme.test').one()
        employee = Employee.query.filter_by(user_id=user.id).one()
        assert user.tenant_id == tenant.id
        assert employee.tenant_id == tenant.id
        assert employee.job_title == 'People Operations Analyst'


def test_client_admin_cannot_create_another_client_admin(client, admin_user):
    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/users',
        headers=_csrf_header(client),
        json={
            'email': 'other-admin@acme.test',
            'first_name': 'Other',
            'last_name': 'Admin',
            'roles': ['CLIENT_ADMIN'],
        },
    )

    assert response.status_code == 400
    assert 'CLIENT_ADMIN' in str(response.get_json()['error']['message'])



def test_client_admin_cannot_assign_super_admin(client, admin_user):
    login = client.post(
        '/api/auth/login',
        json={
            'email': 'admin@acme.test',
            'password': 'StrongPass123!',
        },
    )
    assert login.status_code == 200

    response = client.post(
        '/api/users',
        headers=_csrf_header(client),
        json={
            'email': 'platform-admin@acme.test',
            'first_name': 'Platform',
            'last_name': 'Escalation',
            'roles': ['SUPER_ADMIN'],
        },
    )

    assert response.status_code == 400
    message = str(response.get_json()['error']['message'])
    assert 'SUPER_ADMIN' in message


def test_client_admin_cannot_escape_its_tenant(
    client,
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        other_tenant = Tenant(
            name='Other Organization',
            slug='other-organization',
        )
        db.session.add(other_tenant)
        db.session.commit()
        other_tenant_id = str(other_tenant.id)
        expected_tenant_id = str(tenant.id)

    login = client.post(
        '/api/auth/login',
        json={
            'email': 'admin@acme.test',
            'password': 'StrongPass123!',
        },
    )
    assert login.status_code == 200

    response = client.post(
        '/api/users',
        headers=_csrf_header(client),
        json={
            'tenant_id': other_tenant_id,
            'email': 'tenant-bound@acme.test',
            'first_name': 'Tenant',
            'last_name': 'Bound',
            'roles': ['EMPLOYEE'],
            'employee_profile': {
                'employee_number': 'EMP-TENANT-BOUND',
                'hire_date': '2026-07-24',
                'employment_type': 'full_time',
            },
        },
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['tenant_id'] == expected_tenant_id

    with app.app_context():
        user = User.query.filter_by(
            email='tenant-bound@acme.test',
        ).one()
        employee = Employee.query.filter_by(
            user_id=user.id,
        ).one()

        assert str(user.tenant_id) == expected_tenant_id
        assert str(employee.tenant_id) == expected_tenant_id


def test_client_admin_cannot_provision_organization(
    client,
    admin_user,
):
    login = client.post(
        '/api/auth/login',
        json={
            'email': 'admin@acme.test',
            'password': 'StrongPass123!',
        },
    )
    assert login.status_code == 200

    response = client.post(
        '/api/tenants/provision',
        headers=_csrf_header(client),
        json={
            'organization': {
                'name': 'Unauthorized Organization',
                'slug': 'unauthorized-organization',
            },
            'admin': {
                'email': 'admin@unauthorized.test',
                'first_name': 'Unauthorized',
                'last_name': 'Administrator',
            },
        },
    )

    assert response.status_code == 403


def test_provisioning_rolls_back_when_admin_creation_fails(
    client,
    app,
):
    headers = _login_super_admin(client, app)

    response = client.post(
        '/api/tenants/provision',
        headers=headers,
        json={
            'organization': {
                'name': 'Rollback Organization',
                'slug': 'rollback-organization',
            },
            'admin': {
                'email': 'platform@example.com',
                'first_name': 'Duplicate',
                'last_name': 'Administrator',
            },
        },
    )

    assert response.status_code == 400

    with app.app_context():
        tenant = Tenant.query.filter_by(
            slug='rollback-organization',
        ).one_or_none()
        assert tenant is None
