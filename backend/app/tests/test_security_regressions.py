from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import (
    Document,
    Employee,
    EmployeeOnboardingTask,
    JobHistory,
    OnboardingTask,
    OnboardingTemplate,
    SignatureRecipient,
    SignatureRequest,
)
from sqlalchemy import inspect as sa_inspect

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


def _employee_user(app, tenant_id, *, email, number, first_name='Employee'):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant_id,
            'email': email,
            'first_name': first_name,
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant_id,
            user_id=user.id,
            employee_number=number,
            first_name=first_name,
            last_name='User',
            email=email,
            hire_date=date(2026, 1, 1),
        )
        db.session.add(employee)
        db.session.commit()
        return str(user.id), str(employee.id)


def test_employee_cannot_administer_coworker_onboarding(
    app,
    client,
    tenant,
):
    _employee_user(
        app,
        tenant.id,
        email='onboarding.employee@acme.test',
        number='ONB-EMP-1',
        first_name='Ordinary',
    )
    _, coworker_employee_id = _employee_user(
        app,
        tenant.id,
        email='onboarding.coworker@acme.test',
        number='ONB-EMP-2',
        first_name='Coworker',
    )

    with app.app_context():
        template = OnboardingTemplate(
            tenant_id=tenant.id,
            name='Security boundary onboarding',
            description='Used to verify onboarding administration scope.',
        )
        db.session.add(template)
        db.session.flush()
        task = OnboardingTask(
            tenant_id=tenant.id,
            template_id=template.id,
            title='Read policy',
            assignee_role='EMPLOYEE',
            due_days_after_start=0,
        )
        db.session.add(task)
        db.session.flush()
        assignment = EmployeeOnboardingTask(
            tenant_id=tenant.id,
            employee_id=coworker_employee_id,
            task_id=task.id,
            status='pending',
            due_date=date(2026, 8, 20),
        )
        db.session.add(assignment)
        db.session.commit()
        template_id = str(template.id)
        assignment_id = str(assignment.id)

    headers = _login(client, 'onboarding.employee@acme.test')

    responses = {
        'list assignments': client.get('/api/onboarding/assignments'),
        'view summary': client.get('/api/onboarding/summary'),
        'assign coworker': client.post(
            '/api/onboarding/assign',
            headers=headers,
            json={
                'employee_id': coworker_employee_id,
                'template_id': template_id,
            },
        ),
        'update coworker assignment': client.patch(
            f'/api/onboarding/assignments/{assignment_id}',
            headers=headers,
            json={
                'status': 'waived',
                'completion_notes': 'Unauthorized administration attempt',
            },
        ),
    }

    assert {
        action: response.status_code
        for action, response in responses.items()
    } == {
        'list assignments': 403,
        'view summary': 403,
        'assign coworker': 403,
        'update coworker assignment': 403,
    }

    # Self-service task access remains available to an employee.
    own_tasks = client.get('/api/onboarding/my-tasks')
    assert own_tasks.status_code == 200
    assert own_tasks.get_json()['data']['items'] == []



def test_manager_onboarding_scope_is_limited_to_direct_reports(
    app,
    client,
    tenant,
):
    with app.app_context():
        manager_user = register_user({
            'tenant_id': tenant.id,
            'email': 'onboarding.manager@acme.test',
            'first_name': 'Line',
            'last_name': 'Manager',
            'password': 'StrongPass123!',
            'roles': ['MANAGER'],
        })
        manager_employee = Employee(
            tenant_id=tenant.id,
            user_id=manager_user.id,
            employee_number='ONB-MGR-1',
            first_name='Line',
            last_name='Manager',
            email='onboarding.manager@acme.test',
            hire_date=date(2025, 1, 1),
        )
        db.session.add(manager_employee)
        db.session.flush()

        direct_report = Employee(
            tenant_id=tenant.id,
            employee_number='ONB-DIRECT-1',
            first_name='Direct',
            last_name='Report',
            email='onboarding.direct@acme.test',
            hire_date=date(2026, 1, 1),
            manager_id=manager_employee.id,
        )
        unrelated_employee = Employee(
            tenant_id=tenant.id,
            employee_number='ONB-OTHER-1',
            first_name='Other',
            last_name='Employee',
            email='onboarding.other@acme.test',
            hire_date=date(2026, 1, 1),
        )
        template = OnboardingTemplate(
            tenant_id=tenant.id,
            name='Manager scoped onboarding',
        )
        db.session.add_all([direct_report, unrelated_employee, template])
        db.session.flush()
        task = OnboardingTask(
            tenant_id=tenant.id,
            template_id=template.id,
            title='Manager welcome',
            assignee_role='MANAGER',
            due_days_after_start=1,
        )
        db.session.add(task)
        db.session.flush()
        unrelated_assignment = EmployeeOnboardingTask(
            tenant_id=tenant.id,
            employee_id=unrelated_employee.id,
            task_id=task.id,
            status='pending',
            due_date=date(2026, 8, 20),
        )
        db.session.add(unrelated_assignment)
        db.session.commit()
        direct_report_id = str(direct_report.id)
        unrelated_employee_id = str(unrelated_employee.id)
        unrelated_assignment_id = str(unrelated_assignment.id)
        template_id = str(template.id)

    headers = _login(client, 'onboarding.manager@acme.test')

    allowed = client.post(
        '/api/onboarding/assign',
        headers=headers,
        json={
            'employee_id': direct_report_id,
            'template_id': template_id,
        },
    )
    assert allowed.status_code == 201

    denied = client.post(
        '/api/onboarding/assign',
        headers=headers,
        json={
            'employee_id': unrelated_employee_id,
            'template_id': template_id,
        },
    )
    assert denied.status_code == 403

    listing = client.get('/api/onboarding/assignments')
    assert listing.status_code == 200
    listed_ids = {
        item['id'] for item in listing.get_json()['data']['items']
    }
    assert unrelated_assignment_id not in listed_ids

def test_employee_can_read_own_but_not_coworker_sensitive_job_history(
    app,
    client,
    tenant,
):
    _, actor_employee_id = _employee_user(
        app,
        tenant.id,
        email='history.employee@acme.test',
        number='HIST-EMP-1',
        first_name='History',
    )
    _, coworker_employee_id = _employee_user(
        app,
        tenant.id,
        email='history.coworker@acme.test',
        number='HIST-EMP-2',
        first_name='Private',
    )

    with app.app_context():
        db.session.add(JobHistory(
            tenant_id=tenant.id,
            employee_id=coworker_employee_id,
            job_title='Senior Analyst',
            start_date=date(2025, 1, 1),
            reason='Compensation adjustment after promotion',
            compensation_band='P4-KES',
        ))
        db.session.commit()

    _login(client, 'history.employee@acme.test')

    own_history = client.get(
        f'/api/employees/{actor_employee_id}/job-history',
    )
    assert own_history.status_code == 200

    coworker_history = client.get(
        f'/api/employees/{coworker_employee_id}/job-history',
    )
    assert coworker_history.status_code == 403


def test_organization_owner_can_open_signature_request_visible_in_list(
    app,
    client,
    tenant,
    admin_user,
):
    admin_user_id = sa_inspect(admin_user).identity[0]

    with app.app_context():
        register_user({
            'tenant_id': tenant.id,
            'email': 'owner.signature@acme.test',
            'first_name': 'Organization',
            'last_name': 'Owner',
            'password': 'StrongPass123!',
            'roles': ['ORGANIZATION_OWNER'],
        })
        signer = register_user({
            'tenant_id': tenant.id,
            'email': 'owner.signature.signer@acme.test',
            'first_name': 'Signature',
            'last_name': 'Signer',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        signer_employee = Employee(
            tenant_id=tenant.id,
            user_id=signer.id,
            employee_number='OWNER-SIGN-1',
            first_name='Signature',
            last_name='Signer',
            email='owner.signature.signer@acme.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add(signer_employee)
        db.session.flush()

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Owner review contract',
            document_type='contract',
            original_filename='owner-review.pdf',
            stored_filename='owner-review-security-test.pdf',
            file_path='/tmp/owner-review-security-test.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='c' * 64,
            signature_status='pending',
            access_level='company_admin',
            status='active',
        )
        db.session.add(document)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document.id,
            created_by_id=admin_user_id,
            subject='Owner review request',
            signing_mode='sequential',
            status='sent',
            current_sequence=1,
            due_at=datetime.utcnow() + timedelta(days=7),
            sent_at=datetime.utcnow(),
        )
        db.session.add(signature_request)
        db.session.flush()
        db.session.add(SignatureRecipient(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            user_id=signer.id,
            employee_id=signer_employee.id,
            name=signer_employee.full_name,
            email=signer_employee.email,
            sequence=1,
            status='notified',
        ))
        db.session.commit()
        request_id = str(signature_request.id)

    _login(client, 'owner.signature@acme.test')

    listing = client.get('/api/signature-requests')
    assert listing.status_code == 200
    assert request_id in {
        item['id'] for item in listing.get_json()['data']['items']
    }

    details = client.get(f'/api/signature-requests/{request_id}')
    assert details.status_code == 200

    evidence = client.get(f'/api/signature-requests/{request_id}/evidence')
    assert evidence.status_code == 200
