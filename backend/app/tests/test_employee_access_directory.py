from datetime import date

from app.extensions import db
from app.models import AuthSession, Employee, Tenant, User
from app.models.base import utcnow
from app.services.auth_service import register_user


def _employee(
    tenant_id,
    number,
    email,
    *,
    first_name='Access',
    last_name='Employee',
    user_id=None,
):
    return Employee(
        tenant_id=tenant_id,
        user_id=user_id,
        employee_number=number,
        first_name=first_name,
        last_name=last_name,
        email=email,
        hire_date=date(2026, 1, 1),
        employment_status='active',
    )


def test_employee_access_directory_includes_people_without_accounts_and_access_state(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        active_user = register_user({
            'tenant_id': tenant.id,
            'email': 'access-active@acme.test',
            'first_name': 'Active',
            'last_name': 'Employee',
            'password': 'StrongAccessPass123!',
            'roles': ['MANAGER'],
        })
        invited_user = register_user({
            'tenant_id': tenant.id,
            'email': 'access-invited@acme.test',
            'first_name': 'Invited',
            'last_name': 'Employee',
            'password': 'StrongAccessPass123!',
            'roles': ['EMPLOYEE'],
        })
        invited_user.activation_required = True
        invited_user.invited_at = utcnow()
        invited_user.invitation_sent_at = utcnow()

        inactive_user = register_user({
            'tenant_id': tenant.id,
            'email': 'access-inactive@acme.test',
            'first_name': 'Inactive',
            'last_name': 'Employee',
            'password': 'StrongAccessPass123!',
            'roles': ['EMPLOYEE'],
        })
        inactive_user.is_active = False

        employees = [
            _employee(tenant.id, 'ACCESS-001', 'access-none@acme.test', first_name='No Access'),
            _employee(tenant.id, 'ACCESS-002', active_user.email, first_name='Active', user_id=active_user.id),
            _employee(tenant.id, 'ACCESS-003', invited_user.email, first_name='Invited', user_id=invited_user.id),
            _employee(tenant.id, 'ACCESS-004', inactive_user.email, first_name='Inactive', user_id=inactive_user.id),
        ]
        db.session.add_all(employees)

        other_tenant = Tenant(name='Other Access Tenant', slug='other-access-tenant')
        db.session.add(other_tenant)
        db.session.flush()
        db.session.add(
            _employee(
                other_tenant.id,
                'ACCESS-OTHER',
                'access-other@acme.test',
                first_name='Other Tenant',
            )
        )
        db.session.commit()

    response = client.get(
        '/api/employees/access-directory?per_page=20&sort=full_name&direction=asc',
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.get_json()['data']
    by_number = {item['employee_number']: item for item in data['items']}

    assert 'ACCESS-OTHER' not in by_number
    assert by_number['ACCESS-001']['access'] is None
    assert by_number['ACCESS-002']['access']['status'] == 'active'
    assert by_number['ACCESS-002']['access']['roles'] == ['MANAGER']
    assert by_number['ACCESS-003']['access']['status'] == 'invited'
    assert by_number['ACCESS-003']['access']['invitation_sent_at'] is not None
    assert by_number['ACCESS-004']['access']['status'] == 'suspended'

    no_access = client.get(
        '/api/employees/access-directory?access_status=none',
        headers=auth_headers,
    ).get_json()['data']
    assert no_access['meta']['total'] == 1
    assert no_access['items'][0]['employee_number'] == 'ACCESS-001'


def test_existing_employee_can_be_provisioned_without_duplicated_identity_or_password(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        employee = _employee(
            tenant.id,
            'ACCESS-GRANT',
            'access-grant@acme.test',
            first_name='Grant',
            last_name='Access',
        )
        db.session.add(employee)
        db.session.commit()
        employee_id = employee.id

    response = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=auth_headers,
        json={'roles': ['MANAGER']},
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['user']['email'] == 'access-grant@acme.test'
    assert data['user']['first_name'] == 'Grant'
    assert data['user']['last_name'] == 'Access'
    assert data['user']['roles'] == ['MANAGER']
    assert data['employee']['user_id'] == data['user']['id']


def test_employee_access_update_revokes_sessions_without_changing_employment_status(
    client,
    app,
    tenant,
    auth_headers,
):
    password = 'StrongAccessLifecyclePass123!'
    with app.app_context():
        target = register_user({
            'tenant_id': tenant.id,
            'email': 'access-lifecycle@acme.test',
            'first_name': 'Access',
            'last_name': 'Lifecycle',
            'password': password,
            'roles': ['EMPLOYEE'],
        })
        employee = _employee(
            tenant.id,
            'ACCESS-LIFECYCLE',
            target.email,
            first_name='Access',
            last_name='Lifecycle',
            user_id=target.id,
        )
        db.session.add(employee)
        db.session.commit()
        target_id = target.id
        employee_id = employee.id

    target_client = app.test_client()
    login = target_client.post(
        '/api/auth/login',
        json={'email': 'access-lifecycle@acme.test', 'password': password},
    )
    assert login.status_code == 200

    response = client.patch(
        f'/api/employees/{employee_id}/access',
        headers=auth_headers,
        json={'roles': ['MANAGER'], 'is_active': False},
    )

    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['access']['status'] == 'suspended'
    assert data['access']['roles'] == ['MANAGER']
    assert data['revoked_sessions'] == 1

    with app.app_context():
        target = db.session.get(User, target_id)
        employee = db.session.get(Employee, employee_id)
        session = AuthSession.query.filter_by(user_id=target_id).one()

        assert target.is_active is False
        assert target.role_names == ['MANAGER']
        assert employee.employment_status == 'active'
        assert session.revoked_at is not None
        assert session.revoked_reason == 'employee_access_deactivated_by_administrator'

    blocked = app.test_client().post(
        '/api/auth/login',
        json={'email': 'access-lifecycle@acme.test', 'password': password},
    )
    assert blocked.status_code == 403
    assert blocked.get_json()['error']['code'] == 'ACCOUNT_INACTIVE'
