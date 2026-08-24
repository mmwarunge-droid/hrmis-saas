from datetime import date

from app.extensions import db
from app.models import Employee, Tenant


def _configure_warning_titles(app, tenant_id, titles):
    with app.app_context():
        tenant = db.session.get(Tenant, tenant_id)
        tenant.duplicate_job_title_warning_titles = list(titles)
        db.session.commit()


def _employee_payload(**overrides):
    payload = {
        'employee_number': 'EMP-001',
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'jane@example.test',
        'hire_date': '2026-01-01',
        'job_title': 'CEO',
    }
    payload.update(overrides)
    return payload


def _create_employee(client, auth_headers, **overrides):
    response = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(**overrides),
    )
    assert response.status_code == 201
    return response.get_json()['data']


def test_configured_duplicate_job_title_requires_confirmation_on_create(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='first-ceo@example.test',
        first_name='First',
    )

    response = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-002',
            email='second-ceo@example.test',
            first_name='Second',
            job_title=' ceo ',
        ),
    )

    assert response.status_code == 409
    assert response.get_json()['error'] == {
        'code': 'DUPLICATE_JOB_TITLE_CONFIRMATION_REQUIRED',
        'message': (
            'This organization already has an employee assigned '
            'to the job title ceo. '
            'Are you sure you want to continue?'
        ),
    }

    confirmed = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-002',
            email='second-ceo@example.test',
            first_name='Second',
            job_title=' ceo ',
            confirm_duplicate_job_title=True,
        ),
    )

    assert confirmed.status_code == 201
    assert confirmed.get_json()['data']['job_title'] == 'ceo'


def test_unconfigured_duplicate_job_title_remains_allowed(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='first-analyst@example.test',
        job_title='Analyst',
    )

    duplicate = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-002',
            email='second-analyst@example.test',
            job_title='Analyst',
        ),
    )

    assert duplicate.status_code == 201


def test_terminated_employee_does_not_occupy_warning_job_title(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    existing = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='former-ceo@example.test',
        job_title='CEO',
    )

    terminated = client.patch(
        f"/api/employees/{existing['id']}",
        headers=auth_headers,
        json={
            'employment_status': 'terminated',
            'change_effective_date': '2026-08-23',
            'change_reason': 'Employment ended',
        },
    )
    assert terminated.status_code == 200

    replacement = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-002',
            email='replacement-ceo@example.test',
            job_title='CEO',
        ),
    )

    assert replacement.status_code == 201


def test_duplicate_warning_is_tenant_scoped(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    with app.app_context():
        other = Tenant(
            name='Other Organization',
            slug='other-job-title-organization',
            duplicate_job_title_warning_titles=['CEO'],
        )
        db.session.add(other)
        db.session.flush()

        db.session.add(
            Employee(
                tenant_id=other.id,
                employee_number='OTHER-001',
                first_name='Other',
                last_name='Executive',
                email='ceo@other.test',
                hire_date=date(2026, 1, 1),
                job_title='CEO',
            )
        )
        db.session.commit()

    response = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-001',
            email='ceo@own.test',
            job_title='CEO',
        ),
    )

    assert response.status_code == 201


def test_job_title_change_requires_confirmation_on_update(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='existing-ceo@example.test',
        first_name='Existing',
        job_title='CEO',
    )

    employee = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-002',
        email='analyst@example.test',
        first_name='Analyst',
        job_title='Analyst',
    )

    response = client.patch(
        f"/api/employees/{employee['id']}",
        headers=auth_headers,
        json={
            'job_title': 'CEO',
            'change_effective_date': '2026-08-23',
            'change_reason': 'Promotion',
        },
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == (
        'DUPLICATE_JOB_TITLE_CONFIRMATION_REQUIRED'
    )

    confirmed = client.patch(
        f"/api/employees/{employee['id']}",
        headers=auth_headers,
        json={
            'job_title': 'CEO',
            'change_effective_date': '2026-08-23',
            'change_reason': 'Promotion',
            'confirm_duplicate_job_title': True,
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.get_json()['data']['job_title'] == 'CEO'


def test_unchanged_configured_job_title_does_not_reprompt_on_update(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    first = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='first-ceo@example.test',
        job_title='CEO',
    )

    second_response = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-002',
            email='second-ceo@example.test',
            job_title='CEO',
            confirm_duplicate_job_title=True,
        ),
    )
    assert second_response.status_code == 201
    second = second_response.get_json()['data']

    update = client.patch(
        f"/api/employees/{second['id']}",
        headers=auth_headers,
        json={
            'first_name': 'Updated',
            'job_title': 'CEO',
        },
    )

    assert update.status_code == 200
    assert update.get_json()['data']['first_name'] == 'Updated'

    with app.app_context():
        assert db.session.get(Employee, first['id']) is not None


def test_reactivating_terminated_employee_requires_duplicate_confirmation(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CEO'])

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-001',
        email='active-ceo@example.test',
        first_name='Active',
        job_title='CEO',
    )

    terminated = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-002',
        email='former-ceo@example.test',
        first_name='Former',
        job_title='CEO',
        employment_status='terminated',
    )

    response = client.patch(
        f"/api/employees/{terminated['id']}",
        headers=auth_headers,
        json={
            'employment_status': 'active',
            'change_effective_date': '2026-08-24',
            'change_reason': 'Reactivated',
        },
    )

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == (
        'DUPLICATE_JOB_TITLE_CONFIRMATION_REQUIRED'
    )

    confirmed = client.patch(
        f"/api/employees/{terminated['id']}",
        headers=auth_headers,
        json={
            'employment_status': 'active',
            'change_effective_date': '2026-08-24',
            'change_reason': 'Reactivated',
            'confirm_duplicate_job_title': True,
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.get_json()['data']['employment_status'] == 'active'


def test_inactive_and_suspended_employees_do_not_occupy_warning_job_titles(
    app,
    client,
    tenant,
    auth_headers,
):
    _configure_warning_titles(app, tenant.id, ['CFO', 'COO'])

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-101',
        email='inactive-cfo@example.test',
        first_name='Inactive',
        job_title='CFO',
        employment_status='inactive',
    )

    cfo_replacement = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-102',
            email='active-cfo@example.test',
            first_name='Active',
            job_title='CFO',
            employment_status='active',
        ),
    )

    assert cfo_replacement.status_code == 201

    _create_employee(
        client,
        auth_headers,
        employee_number='EMP-103',
        email='suspended-coo@example.test',
        first_name='Suspended',
        job_title='COO',
        employment_status='suspended',
    )

    coo_replacement = client.post(
        '/api/employees',
        headers=auth_headers,
        json=_employee_payload(
            employee_number='EMP-104',
            email='active-coo@example.test',
            first_name='Active',
            job_title='COO',
            employment_status='active',
        ),
    )

    assert coo_replacement.status_code == 201
