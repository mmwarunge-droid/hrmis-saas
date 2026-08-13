from datetime import date

from app.extensions import db
from app.models import Employee, Tenant
from app.services.auth_service import register_user


def _login(client, email, password='StrongPass123!'):
    response = client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    csrf_cookie = client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None
    return {'X-CSRF-TOKEN': csrf_cookie.value}


def _seed_employee_user_link_boundary(app, tenant_id):
    with app.app_context():
        admin = register_user({
            'tenant_id': tenant_id,
            'email': 'employee-link.admin@acme.test',
            'first_name': 'Employee',
            'last_name': 'Admin',
            'password': 'StrongPass123!',
            'roles': ['CLIENT_ADMIN'],
        })
        local_user = register_user({
            'tenant_id': tenant_id,
            'email': 'employee-link.local@acme.test',
            'first_name': 'Local',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        other_tenant = Tenant(
            name='Employee Link Other Tenant',
            slug='employee-link-other-tenant',
            country='Kenya',
        )
        db.session.add(other_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': other_tenant.id,
            'email': 'employee-link.foreign@other.test',
            'first_name': 'Foreign',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        unlinked_employee = Employee(
            tenant_id=tenant_id,
            employee_number='EMP-LINK-EXISTING',
            first_name='Existing',
            last_name='Employee',
            email='employee-link.existing@acme.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add(unlinked_employee)
        db.session.commit()

        return {
            'admin_email': admin.email,
            'local_user_id': str(local_user.id),
            'foreign_user_id': str(foreign_user.id),
            'existing_employee_id': str(unlinked_employee.id),
        }


def test_employee_create_rejects_cross_tenant_user_link(
    app,
    client,
    tenant,
):
    seeded = _seed_employee_user_link_boundary(app, tenant.id)
    headers = _login(client, seeded['admin_email'])

    response = client.post(
        '/api/employees',
        headers=headers,
        json={
            'user_id': seeded['foreign_user_id'],
            'employee_number': 'EMP-LINK-CREATE-XTENANT',
            'first_name': 'Cross',
            'last_name': 'Tenant',
            'email': 'employee-link.create-cross@acme.test',
            'hire_date': '2026-02-01',
        },
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'EMPLOYEE_CREATE_FAILED'

    with app.app_context():
        employee = Employee.query.filter_by(
            tenant_id=tenant.id,
            employee_number='EMP-LINK-CREATE-XTENANT',
        ).first()
        assert employee is None


def test_employee_update_rejects_cross_tenant_user_link(
    app,
    client,
    tenant,
):
    seeded = _seed_employee_user_link_boundary(app, tenant.id)
    headers = _login(client, seeded['admin_email'])

    response = client.patch(
        f"/api/employees/{seeded['existing_employee_id']}",
        headers=headers,
        json={'user_id': seeded['foreign_user_id']},
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'EMPLOYEE_UPDATE_FAILED'

    with app.app_context():
        employee = db.session.get(
            Employee,
            seeded['existing_employee_id'],
        )
        assert employee.user_id is None


def test_employee_create_retains_same_tenant_user_link(
    app,
    client,
    tenant,
):
    seeded = _seed_employee_user_link_boundary(app, tenant.id)
    headers = _login(client, seeded['admin_email'])

    response = client.post(
        '/api/employees',
        headers=headers,
        json={
            'user_id': seeded['local_user_id'],
            'employee_number': 'EMP-LINK-CREATE-LOCAL',
            'first_name': 'Local',
            'last_name': 'Employee',
            'email': 'employee-link.create-local@acme.test',
            'hire_date': '2026-02-01',
        },
    )

    assert response.status_code == 201
    assert response.get_json()['data']['user_id'] == seeded['local_user_id']

    with app.app_context():
        employee = Employee.query.filter_by(
            tenant_id=tenant.id,
            employee_number='EMP-LINK-CREATE-LOCAL',
        ).first()
        assert employee is not None
        assert str(employee.user_id) == seeded['local_user_id']
