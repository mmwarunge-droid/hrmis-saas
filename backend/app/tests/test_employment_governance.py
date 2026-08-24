from app.extensions import db
from app.models import AuditLog, Tenant
from app.services.auth_service import register_user


def _login_as(
    app,
    *,
    email,
    password,
    roles,
    tenant_id=None,
):
    with app.app_context():
        payload = {
            'email': email,
            'first_name': 'Governance',
            'last_name': 'Tester',
            'password': password,
            'roles': roles,
        }
        if tenant_id is not None:
            payload['tenant_id'] = tenant_id
        register_user(payload)

    client = app.test_client()
    response = client.post(
        '/api/auth/login',
        json={
            'email': email,
            'password': password,
        },
    )
    assert response.status_code == 200

    csrf_cookie = client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None

    return client, {'X-CSRF-TOKEN': csrf_cookie.value}


def test_client_admin_can_read_and_update_own_employment_governance(
    app,
    client,
    tenant,
    auth_headers,
):
    url = f'/api/tenants/{tenant.id}/employment-governance'

    get_response = client.get(url, headers=auth_headers)

    assert get_response.status_code == 200
    assert get_response.get_json()['data'] == {
        'duplicate_job_title_warning_titles': [],
    }

    update_response = client.patch(
        url,
        headers=auth_headers,
        json={
            'duplicate_job_title_warning_titles': [
                ' CEO ',
                'ceo',
                'Chief Financial Officer',
                ' chief financial officer ',
                'Managing Director',
            ],
        },
    )

    assert update_response.status_code == 200
    assert update_response.get_json()['data'] == {
        'duplicate_job_title_warning_titles': [
            'CEO',
            'Chief Financial Officer',
            'Managing Director',
        ],
    }

    with app.app_context():
        saved = db.session.get(Tenant, tenant.id)
        assert saved.duplicate_job_title_warning_titles == [
            'CEO',
            'Chief Financial Officer',
            'Managing Director',
        ]

        event = AuditLog.query.filter_by(
            action='tenant.employment_governance_update',
            tenant_id=tenant.id,
        ).one()
        assert event.entity_type == 'Tenant'
        assert str(event.entity_id) == str(tenant.id)


def test_employment_governance_accepts_empty_warning_title_list(
    app,
    client,
    tenant,
    auth_headers,
):
    url = f'/api/tenants/{tenant.id}/employment-governance'

    with app.app_context():
        saved = db.session.get(Tenant, tenant.id)
        saved.duplicate_job_title_warning_titles = ['CEO']
        db.session.commit()

    response = client.patch(
        url,
        headers=auth_headers,
        json={'duplicate_job_title_warning_titles': []},
    )

    assert response.status_code == 200
    assert response.get_json()['data'] == {
        'duplicate_job_title_warning_titles': [],
    }

    with app.app_context():
        saved = db.session.get(Tenant, tenant.id)
        assert saved.duplicate_job_title_warning_titles == []


def test_employment_governance_rejects_blank_warning_title(
    app,
    client,
    tenant,
    auth_headers,
):
    response = client.patch(
        f'/api/tenants/{tenant.id}/employment-governance',
        headers=auth_headers,
        json={
            'duplicate_job_title_warning_titles': [
                'CEO',
                '   ',
            ],
        },
    )

    assert response.status_code == 422

    with app.app_context():
        saved = db.session.get(Tenant, tenant.id)
        assert saved.duplicate_job_title_warning_titles == []


def test_client_admin_cannot_manage_another_tenant(
    app,
    client,
    auth_headers,
):
    with app.app_context():
        other = Tenant(
            name='Other Organization',
            slug='other-organization',
        )
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    get_response = client.get(
        f'/api/tenants/{other_id}/employment-governance',
        headers=auth_headers,
    )
    patch_response = client.patch(
        f'/api/tenants/{other_id}/employment-governance',
        headers=auth_headers,
        json={'duplicate_job_title_warning_titles': ['CEO']},
    )

    assert get_response.status_code == 403
    assert patch_response.status_code == 403


def test_employee_role_cannot_manage_employment_governance(
    app,
    tenant,
):
    employee_client, headers = _login_as(
        app,
        tenant_id=tenant.id,
        email='governance-employee@example.test',
        password='StrongEmployeePass123!',
        roles=['EMPLOYEE'],
    )

    url = f'/api/tenants/{tenant.id}/employment-governance'

    get_response = employee_client.get(url, headers=headers)
    patch_response = employee_client.patch(
        url,
        headers=headers,
        json={'duplicate_job_title_warning_titles': ['CEO']},
    )

    assert get_response.status_code == 403
    assert patch_response.status_code == 403


def test_super_admin_can_manage_selected_tenant(
    app,
    tenant,
):
    super_client, headers = _login_as(
        app,
        email='governance-platform@example.test',
        password='StrongPlatformPass123!',
        roles=['SUPER_ADMIN'],
    )

    response = super_client.patch(
        f'/api/tenants/{tenant.id}/employment-governance',
        headers=headers,
        json={
            'duplicate_job_title_warning_titles': [
                'Chief Executive Officer',
            ],
        },
    )

    assert response.status_code == 200
    assert response.get_json()['data'] == {
        'duplicate_job_title_warning_titles': [
            'Chief Executive Officer',
        ],
    }

    with app.app_context():
        saved = db.session.get(Tenant, tenant.id)
        assert saved.duplicate_job_title_warning_titles == [
            'Chief Executive Officer',
        ]
