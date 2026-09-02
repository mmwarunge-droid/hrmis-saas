from datetime import date

from app.extensions import db
from app.models import Employee, Tenant
from app.services.auth_service import register_user


USER_CONFLICT_CODE = 'EMAIL_ALREADY_REGISTERED'


def _user_payload(email, *, employee_profile=None):
    payload = {
        'email': email,
        'first_name': 'Duplicate',
        'last_name': 'Check',
        'roles': ['EMPLOYEE'],
    }
    if employee_profile is not None:
        payload['employee_profile'] = employee_profile
    return payload


def _employee_payload(email, number='EMP-EMAIL-001'):
    return {
        'employee_number': number,
        'first_name': 'Email',
        'last_name': 'Check',
        'email': email,
        'hire_date': '2026-09-01',
        'job_title': 'Analyst',
    }


def test_user_creation_normalizes_email_and_blocks_case_space_duplicate(
    client,
    auth_headers,
):
    created = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload('  Unique.Person@Acme.Test  '),
    )
    assert created.status_code == 201
    assert created.get_json()['data']['email'] == 'unique.person@acme.test'

    duplicate = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload('UNIQUE.PERSON@ACME.TEST'),
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_user_email_availability_is_normalized_and_does_not_expose_record_details(
    client,
    auth_headers,
    admin_user,
):
    response = client.get(
        '/api/users/email-availability',
        headers=auth_headers,
        query_string={'email': '  ADMIN@ACME.TEST  '},
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['available'] is False
    assert data['code'] == USER_CONFLICT_CODE
    assert 'tenant_id' not in data
    assert 'user_id' not in data

    available = client.get(
        '/api/users/email-availability',
        headers=auth_headers,
        query_string={'email': 'new.identity@acme.test'},
    )
    assert available.status_code == 200
    assert available.get_json()['data']['available'] is True


def test_user_creation_with_employee_profile_keeps_one_normalized_identity(
    client,
    auth_headers,
):
    response = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload(
            '  Profile.Identity@Acme.Test ',
            employee_profile={
                'employee_number': 'EMP-PROFILE-EMAIL',
                'hire_date': '2026-09-01',
                'job_title': 'Consultant',
            },
        ),
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['email'] == 'profile.identity@acme.test'
    assert data['employee_profile']['email'] == 'profile.identity@acme.test'


def test_user_creation_rejects_same_tenant_employee_email(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='EMP-EXISTING-EMAIL',
            first_name='Existing',
            last_name='Employee',
            email='existing.employee@acme.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add(employee)
        db.session.commit()

    response = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload(' EXISTING.EMPLOYEE@ACME.TEST '),
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_employee_creation_normalizes_email_and_blocks_case_space_duplicate(
    client,
    auth_headers,
):
    created = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload('  Employee.Email@Acme.Test  '),
    )
    assert created.status_code == 201
    assert created.get_json()['data']['email'] == 'employee.email@acme.test'

    duplicate = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            'EMPLOYEE.EMAIL@ACME.TEST',
            number='EMP-EMAIL-002',
        ),
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_employee_email_availability_rejects_global_user_collision(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Email Tenant',
            slug='foreign-email-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()
        register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'shared.identity@example.test',
            'first_name': 'Foreign',
            'last_name': 'Identity',
            'password': 'StrongSharedIdentityPass123!',
            'roles': ['EMPLOYEE'],
        })

    availability = client.get(
        '/api/employees/email-availability',
        headers=auth_headers,
        query_string={'email': ' SHARED.IDENTITY@EXAMPLE.TEST '},
    )
    assert availability.status_code == 200
    assert availability.get_json()['data']['available'] is False

    created = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            'shared.identity@example.test',
            number='EMP-CROSS-TENANT-COLLISION',
        ),
    )
    assert created.status_code == 409
    assert created.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_login_and_password_reset_accept_canonical_email_variants(
    client,
    app,
    admin_user,
):
    login = client.post(
        '/api/auth/login',
        json={
            'email': '  ADMIN@ACME.TEST  ',
            'password': 'StrongPass123!',
        },
    )
    assert login.status_code == 200

    with app.app_context():
        outbox_before = len(
            app.extensions.get('mail_outbox', [])
        )

    reset = client.post(
        '/api/auth/password/forgot',
        json={'email': '  ADMIN@ACME.TEST  '},
    )
    assert reset.status_code == 202

    with app.app_context():
        outbox = app.extensions.get('mail_outbox', [])
        assert len(outbox) == outbox_before + 1
        assert outbox[-1]['to'] == 'admin@acme.test'


def test_soft_deleted_user_email_is_not_reused(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant.id,
            'email': 'historical.identity@acme.test',
            'first_name': 'Historical',
            'last_name': 'Identity',
            'password': 'StrongHistoricalIdentityPass123!',
            'roles': ['EMPLOYEE'],
        })
        user.soft_delete()
        db.session.commit()

    response = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload('HISTORICAL.IDENTITY@ACME.TEST'),
    )
    assert response.status_code == 409
    assert response.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_email_duplicate_controls_require_administrative_permissions(
    client,
    app,
    tenant,
):
    with app.app_context():
        register_user({
            'tenant_id': tenant.id,
            'email': 'ordinary.employee@acme.test',
            'first_name': 'Ordinary',
            'last_name': 'Employee',
            'password': 'StrongOrdinaryEmployeePass123!',
            'roles': ['EMPLOYEE'],
        })

    login = client.post(
        '/api/auth/login',
        json={
            'email': 'ordinary.employee@acme.test',
            'password': 'StrongOrdinaryEmployeePass123!',
        },
    )
    assert login.status_code == 200
    csrf = client.get_cookie('csrf_access_token')
    headers = {'X-CSRF-TOKEN': csrf.value}

    assert client.get(
        '/api/users/email-availability',
        query_string={'email': 'target@acme.test'},
    ).status_code == 403
    assert client.get(
        '/api/employees/email-availability',
        query_string={'email': 'target@acme.test'},
    ).status_code == 403
    assert client.post(
        '/api/users',
        headers=headers,
        json=_user_payload('target@acme.test'),
    ).status_code == 403
    assert client.post(
        '/api/employees',
        headers=headers,
        json=_employee_payload('target@acme.test'),
    ).status_code == 403


def test_user_creation_rejects_employee_email_from_another_tenant(
    client,
    app,
    auth_headers,
):
    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Employee Tenant',
            slug='foreign-employee-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()
        db.session.add(Employee(
            tenant_id=foreign_tenant.id,
            employee_number='FOREIGN-EMP-EMAIL',
            first_name='Foreign',
            last_name='Employee',
            email='employee.in.other.tenant@example.test',
            hire_date=date(2026, 1, 1),
        ))
        db.session.commit()

    response = client.post(
        '/api/users',
        headers=auth_headers,
        json=_user_payload(' EMPLOYEE.IN.OTHER.TENANT@EXAMPLE.TEST '),
    )
    assert response.status_code == 409
    assert response.get_json()['error']['code'] == USER_CONFLICT_CODE


def test_access_provisioning_rejects_email_shared_by_another_employee_record(
    client,
    app,
    tenant,
    auth_headers,
):
    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Access Tenant',
            slug='foreign-access-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        shared_email = 'multi.employee@example.test'
        local_employee = Employee(
            tenant_id=tenant.id,
            employee_number='LOCAL-MULTI-EMAIL',
            first_name='Local',
            last_name='Employee',
            email=shared_email,
            hire_date=date(2026, 1, 1),
        )
        foreign_employee = Employee(
            tenant_id=foreign_tenant.id,
            employee_number='FOREIGN-MULTI-EMAIL',
            first_name='Foreign',
            last_name='Employee',
            email=shared_email,
            hire_date=date(2026, 1, 1),
        )
        db.session.add_all([local_employee, foreign_employee])
        db.session.commit()
        local_employee_id = str(local_employee.id)

    response = client.post(
        f'/api/employees/{local_employee_id}/provision-access',
        headers=auth_headers,
        json={'roles': ['EMPLOYEE']},
    )
    assert response.status_code == 409
    assert response.get_json()['error']['code'] == USER_CONFLICT_CODE
