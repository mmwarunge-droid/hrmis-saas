from datetime import date

from app.extensions import db
from app.models import (
    Document,
    Employee,
    Goal,
    OnboardingTemplate,
    SignatureRequest,
    Tenant,
)
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


def _seed_platform_scope(app, first_tenant_id):
    with app.app_context():
        second_tenant = Tenant(
            name='Beta Ltd',
            slug='beta-security-boundary',
            country='Kenya',
        )
        db.session.add(second_tenant)
        db.session.flush()

        register_user({
            'tenant_id': None,
            'email': 'platform.boundary@kinetic.test',
            'first_name': 'Platform',
            'last_name': 'Boundary',
            'password': 'StrongPass123!',
            'roles': ['SUPER_ADMIN'],
        })

        first_employee = Employee(
            tenant_id=first_tenant_id,
            employee_number='BOUNDARY-A-1',
            first_name='Tenant',
            last_name='Alpha',
            email='tenant.alpha@acme.test',
            hire_date=date(2026, 1, 1),
        )
        second_employee = Employee(
            tenant_id=second_tenant.id,
            employee_number='BOUNDARY-B-1',
            first_name='Tenant',
            last_name='Beta',
            email='tenant.beta@beta.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add_all([first_employee, second_employee])

        first_goal = Goal(
            tenant_id=first_tenant_id,
            title='Alpha organization goal',
            owner_type='organization',
            target_value=100,
            current_value=10,
            unit='%',
            start_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
            progress_percent=10,
        )
        second_goal = Goal(
            tenant_id=second_tenant.id,
            title='Beta organization goal',
            owner_type='organization',
            target_value=100,
            current_value=20,
            unit='%',
            start_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
            progress_percent=20,
        )
        db.session.add_all([first_goal, second_goal])

        first_document = Document(
            tenant_id=first_tenant_id,
            title='Alpha policy',
            document_type='policy',
            original_filename='alpha-policy.pdf',
            stored_filename='alpha-policy-boundary.pdf',
            file_path='/tmp/alpha-policy-boundary.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='a' * 64,
            access_level='company_admin',
            status='active',
        )
        second_document = Document(
            tenant_id=second_tenant.id,
            title='Beta policy',
            document_type='policy',
            original_filename='beta-policy.pdf',
            stored_filename='beta-policy-boundary.pdf',
            file_path='/tmp/beta-policy-boundary.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='b' * 64,
            access_level='company_admin',
            status='active',
        )
        db.session.add_all([first_document, second_document])
        db.session.flush()

        first_template = OnboardingTemplate(
            tenant_id=first_tenant_id,
            name='Alpha onboarding',
        )
        second_template = OnboardingTemplate(
            tenant_id=second_tenant.id,
            name='Beta onboarding',
        )
        db.session.add_all([first_template, second_template])

        first_signature = SignatureRequest(
            tenant_id=first_tenant_id,
            document_id=first_document.id,
            subject='Alpha signature request',
            status='sent',
            due_at=None,
        )
        second_signature = SignatureRequest(
            tenant_id=second_tenant.id,
            document_id=second_document.id,
            subject='Beta signature request',
            status='sent',
            due_at=None,
        )
        db.session.add_all([first_signature, second_signature])
        db.session.commit()

        return {
            'first_tenant_id': str(first_tenant_id),
            'second_tenant_id': str(second_tenant.id),
            'second_signature_id': str(second_signature.id),
        }


def test_super_admin_requires_tenant_context_for_tenant_scoped_reads(
    app,
    client,
    tenant,
):
    _seed_platform_scope(app, tenant.id)
    _login(client, 'platform.boundary@kinetic.test')

    endpoints = [
        '/api/employees',
        '/api/employees/summary',
        '/api/goals',
        '/api/goals/summary',
        '/api/documents',
        '/api/documents/summary',
        '/api/onboarding/templates',
        '/api/onboarding/assignments',
        '/api/onboarding/summary',
        '/api/signature-requests',
        '/api/leave/requests',
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 422, endpoint
        assert response.get_json()['error']['code'] == (
            'TENANT_CONTEXT_REQUIRED'
        ), endpoint


def test_super_admin_tenant_context_scopes_cross_module_lists(
    app,
    client,
    tenant,
):
    seeded = _seed_platform_scope(app, tenant.id)
    _login(client, 'platform.boundary@kinetic.test')
    tenant_id = seeded['first_tenant_id']

    employees = client.get(f'/api/employees?tenant_id={tenant_id}')
    assert employees.status_code == 200
    employee_data = employees.get_json()['data']
    assert employee_data['meta']['total'] == 1
    assert {
        item['tenant_id']
        for item in employee_data['items']
    } == {tenant_id}

    goals = client.get(f'/api/goals?tenant_id={tenant_id}')
    assert goals.status_code == 200
    goal_data = goals.get_json()['data']
    assert goal_data['meta']['total'] == 1
    assert [item['title'] for item in goal_data['items']] == [
        'Alpha organization goal'
    ]

    documents = client.get(
        f'/api/documents?tenant_id={tenant_id}',
    )
    assert documents.status_code == 200
    document_data = documents.get_json()['data']
    assert document_data['meta']['total'] == 1
    assert [item['title'] for item in document_data['items']] == [
        'Alpha policy'
    ]

    templates = client.get(
        f'/api/onboarding/templates?tenant_id={tenant_id}',
    )
    assert templates.status_code == 200
    template_items = templates.get_json()['data']['items']
    assert [item['name'] for item in template_items] == [
        'Alpha onboarding'
    ]

    signatures = client.get(
        f'/api/signature-requests?tenant_id={tenant_id}',
    )
    assert signatures.status_code == 200
    signature_items = signatures.get_json()['data']['items']
    assert [item['subject'] for item in signature_items] == [
        'Alpha signature request'
    ]


def test_super_admin_active_tenant_blocks_cross_tenant_signature_detail(
    app,
    client,
    tenant,
):
    seeded = _seed_platform_scope(app, tenant.id)
    _login(client, 'platform.boundary@kinetic.test')

    request_id = seeded['second_signature_id']
    active_tenant_id = seeded['first_tenant_id']

    details = client.get(
        f'/api/signature-requests/{request_id}'
        f'?tenant_id={active_tenant_id}',
    )
    assert details.status_code == 404

    evidence = client.get(
        f'/api/signature-requests/{request_id}/evidence'
        f'?tenant_id={active_tenant_id}',
    )
    assert evidence.status_code == 404
