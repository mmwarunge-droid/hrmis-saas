from datetime import date

from app.extensions import db
from app.models import AuditLog, Employee, User
from app.services.auth_service import register_user


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _create_existing_employee(app, tenant_id, email='existing@acme.test', status='active'):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant_id,
            employee_number='EMP-EXISTING',
            first_name='Existing',
            last_name='Employee',
            email=email,
            hire_date=date(2026, 1, 15),
            employment_status=status,
            employment_type='full_time',
            job_title='Operations Analyst',
        )
        db.session.add(employee)
        db.session.commit()
        return str(employee.id)


def test_client_admin_provisions_access_for_existing_employee(client, app, tenant, admin_user):
    employee_id = _create_existing_employee(app, tenant.id)
    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200

    response = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=_csrf_header(client),
        json={
            'password': 'StrongExistingPass123!',
            'roles': ['EMPLOYEE'],
        },
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['user']['email'] == 'existing@acme.test'
    assert data['user']['roles'] == ['EMPLOYEE']
    assert data['employee']['user_id'] == data['user']['id']

    with app.app_context():
        user = User.query.filter_by(email='existing@acme.test').one()
        employee = Employee.query.filter_by(id=employee_id).one()
        assert employee.user_id == user.id
        assert user.tenant_id == tenant.id
        assert AuditLog.query.filter_by(action='employee.access_provisioned').count() == 1


def test_existing_employee_cannot_be_provisioned_twice(client, app, tenant, admin_user):
    employee_id = _create_existing_employee(app, tenant.id)
    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200
    payload = {'password': 'StrongExistingPass123!', 'roles': ['MANAGER']}

    first = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=_csrf_header(client),
        json=payload,
    )
    second = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=_csrf_header(client),
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.get_json()['error']['code'] == 'EMPLOYEE_ACCESS_EXISTS'
    with app.app_context():
        assert User.query.filter_by(email='existing@acme.test').count() == 1


def test_provisioning_rejects_an_email_already_registered_to_another_user(
    client,
    app,
    tenant,
    admin_user,
):
    employee_id = _create_existing_employee(app, tenant.id, email='registered@acme.test')
    with app.app_context():
        register_user({
            'tenant_id': tenant.id,
            'email': 'registered@acme.test',
            'first_name': 'Registered',
            'last_name': 'User',
            'password': 'StrongRegisteredPass123!',
            'roles': ['EMPLOYEE'],
        })

    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200
    response = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=_csrf_header(client),
        json={'password': 'StrongExistingPass123!', 'roles': ['EMPLOYEE']},
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'EMAIL_ALREADY_REGISTERED'
    with app.app_context():
        employee = Employee.query.filter_by(id=employee_id).one()
        assert employee.user_id is None
        assert User.query.filter_by(email='registered@acme.test').count() == 1


def test_terminated_employee_cannot_receive_access(client, app, tenant, admin_user):
    employee_id = _create_existing_employee(app, tenant.id, status='terminated')
    login = client.post(
        '/api/auth/login',
        json={'email': 'admin@acme.test', 'password': 'StrongPass123!'},
    )
    assert login.status_code == 200

    response = client.post(
        f'/api/employees/{employee_id}/provision-access',
        headers=_csrf_header(client),
        json={'password': 'StrongExistingPass123!', 'roles': ['EMPLOYEE']},
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'EMPLOYEE_NOT_ELIGIBLE'
    with app.app_context():
        employee = Employee.query.filter_by(id=employee_id).one()
        assert employee.user_id is None
        assert User.query.filter_by(email='existing@acme.test').count() == 0
