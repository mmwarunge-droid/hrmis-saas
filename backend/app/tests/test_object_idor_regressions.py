from datetime import date

from app.extensions import db
from app.models import (
    Document,
    Employee,
    EmployeeOnboardingTask,
    Goal,
    LeaveRequest,
    LeaveType,
    OnboardingTask,
    OnboardingTemplate,
    SignatureRecipient,
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


def _seed_cross_tenant_objects(app, active_tenant_id):
    with app.app_context():
        other_tenant = Tenant(
            name='IDOR Other Tenant',
            slug='idor-other-tenant',
            country='Kenya',
        )
        db.session.add(other_tenant)
        db.session.flush()

        register_user({
            'tenant_id': None,
            'email': 'idor.platform@kinetic.test',
            'first_name': 'Platform',
            'last_name': 'IDOR',
            'password': 'StrongPass123!',
            'roles': ['SUPER_ADMIN'],
        })
        other_user = register_user({
            'tenant_id': other_tenant.id,
            'email': 'idor.employee@other.test',
            'first_name': 'Other',
            'last_name': 'Employee',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        other_employee = Employee(
            tenant_id=other_tenant.id,
            user_id=other_user.id,
            employee_number='IDOR-B-1',
            first_name='Other',
            last_name='Employee',
            email='idor.employee@other.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add(other_employee)

        other_goal = Goal(
            tenant_id=other_tenant.id,
            title='Other tenant private goal',
            owner_type='organization',
            target_value=100,
            current_value=20,
            unit='%',
            start_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
            progress_percent=20,
        )
        db.session.add(other_goal)

        other_document = Document(
            tenant_id=other_tenant.id,
            title='Other tenant private document',
            document_type='contract',
            original_filename='other-private.pdf',
            stored_filename='other-private-idor.pdf',
            file_path='/tmp/other-private-idor.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='d' * 64,
            access_level='company_admin',
            status='active',
        )
        db.session.add(other_document)
        db.session.flush()

        other_signature = SignatureRequest(
            tenant_id=other_tenant.id,
            document_id=other_document.id,
            subject='Other tenant signature',
            status='sent',
        )
        db.session.add(other_signature)
        db.session.flush()
        other_recipient = SignatureRecipient(
            tenant_id=other_tenant.id,
            signature_request_id=other_signature.id,
            user_id=other_user.id,
            employee_id=other_employee.id,
            name=other_employee.full_name,
            email=other_employee.email,
            sequence=1,
            status='notified',
        )
        db.session.add(other_recipient)

        template = OnboardingTemplate(
            tenant_id=other_tenant.id,
            name='Other tenant onboarding',
        )
        db.session.add(template)
        db.session.flush()
        task = OnboardingTask(
            tenant_id=other_tenant.id,
            template_id=template.id,
            title='Other tenant onboarding task',
            assignee_role='EMPLOYEE',
            due_days_after_start=0,
        )
        db.session.add(task)
        db.session.flush()
        assignment = EmployeeOnboardingTask(
            tenant_id=other_tenant.id,
            employee_id=other_employee.id,
            task_id=task.id,
            status='pending',
            due_date=date(2026, 8, 30),
        )
        db.session.add(assignment)

        leave_type = LeaveType(
            tenant_id=other_tenant.id,
            code='IDOR-LEAVE',
            name='IDOR Leave',
            annual_entitlement_days=20,
        )
        db.session.add(leave_type)
        db.session.flush()
        leave_request = LeaveRequest(
            tenant_id=other_tenant.id,
            employee_id=other_employee.id,
            leave_type_id=leave_type.id,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            total_days=2,
            reason='Private leave request',
            status='pending',
            requested_by_user_id=other_user.id,
        )
        db.session.add(leave_request)
        db.session.commit()

        return {
            'active_tenant_id': str(active_tenant_id),
            'employee_id': str(other_employee.id),
            'goal_id': str(other_goal.id),
            'document_id': str(other_document.id),
            'signature_recipient_id': str(other_recipient.id),
            'onboarding_assignment_id': str(assignment.id),
            'leave_request_id': str(leave_request.id),
        }


def test_selected_tenant_blocks_cross_tenant_object_ids_across_modules(
    app,
    client,
    tenant,
):
    seeded = _seed_cross_tenant_objects(app, tenant.id)
    headers = _login(client, 'idor.platform@kinetic.test')
    tenant_id = seeded['active_tenant_id']

    reads = {
        'employee': client.get(
            f"/api/employees/{seeded['employee_id']}?tenant_id={tenant_id}"
        ),
        'goal': client.get(
            f"/api/goals/{seeded['goal_id']}?tenant_id={tenant_id}"
        ),
        'document': client.get(
            f"/api/documents/{seeded['document_id']}?tenant_id={tenant_id}"
        ),
    }

    assert {
        name: response.status_code
        for name, response in reads.items()
    } == {
        'employee': 404,
        'goal': 404,
        'document': 404,
    }

    onboarding = client.patch(
        '/api/onboarding/tasks/'
        f"{seeded['onboarding_assignment_id']}/complete"
        f'?tenant_id={tenant_id}',
        headers=headers,
        json={'completion_notes': 'Must not cross tenants'},
    )
    assert onboarding.status_code == 404

    leave = client.patch(
        f"/api/leave/requests/{seeded['leave_request_id']}/approve"
        f'?tenant_id={tenant_id}',
        headers=headers,
        json={'decision_notes': 'Must not cross tenants'},
    )
    assert leave.status_code == 404


def test_selected_tenant_blocks_cross_tenant_signature_recipient_reads(
    app,
    client,
    tenant,
):
    seeded = _seed_cross_tenant_objects(app, tenant.id)
    _login(client, 'idor.platform@kinetic.test')
    tenant_id = seeded['active_tenant_id']
    recipient_id = seeded['signature_recipient_id']

    details = client.get(
        f'/api/signature-requests/recipients/{recipient_id}'
        f'?tenant_id={tenant_id}',
    )
    assert details.status_code == 404

    discussion = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/discussion'
        f'?tenant_id={tenant_id}',
    )
    assert discussion.status_code == 404


def test_cross_tenant_signature_recipient_mutation_hides_object_existence(
    app,
    client,
    tenant,
):
    seeded = _seed_cross_tenant_objects(app, tenant.id)
    headers = _login(client, 'idor.platform@kinetic.test')
    tenant_id = seeded['active_tenant_id']
    recipient_id = seeded['signature_recipient_id']

    actions = {
        'viewed': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/viewed'
            f'?tenant_id={tenant_id}',
            headers=headers,
        ),
        'sign': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/sign'
            f'?tenant_id={tenant_id}',
            headers=headers,
            json={'signature_name': 'Platform IDOR'},
        ),
        'decline': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/decline'
            f'?tenant_id={tenant_id}',
            headers=headers,
            json={'reason': 'Cross-tenant action must be hidden'},
        ),
        'comment': client.post(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/comments'
            f'?tenant_id={tenant_id}',
            headers=headers,
            json={'body': 'Cross-tenant comment must be hidden'},
        ),
        'resolve': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/resolve'
            f'?tenant_id={tenant_id}',
            headers=headers,
        ),
    }

    assert {
        name: response.status_code
        for name, response in actions.items()
    } == {
        'viewed': 404,
        'sign': 404,
        'decline': 404,
        'comment': 404,
        'resolve': 404,
    }


def test_super_admin_requires_tenant_context_for_signature_recipient_ids(
    app,
    client,
    tenant,
):
    seeded = _seed_cross_tenant_objects(app, tenant.id)
    headers = _login(client, 'idor.platform@kinetic.test')
    recipient_id = seeded['signature_recipient_id']

    details = client.get(
        f'/api/signature-requests/recipients/{recipient_id}',
    )
    discussion = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/discussion',
    )
    mutations = {
        'viewed': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/viewed',
            headers=headers,
        ),
        'sign': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/sign',
            headers=headers,
            json={'signature_name': 'Platform IDOR'},
        ),
        'decline': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/decline',
            headers=headers,
            json={'reason': 'Tenant context is required'},
        ),
        'comment': client.post(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/comments',
            headers=headers,
            json={'body': 'Tenant context is required'},
        ),
        'resolve': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/resolve',
            headers=headers,
        ),
    }

    assert details.status_code == 422
    assert details.get_json()['error']['code'] == 'TENANT_CONTEXT_REQUIRED'
    assert discussion.status_code == 422
    assert discussion.get_json()['error']['code'] == 'TENANT_CONTEXT_REQUIRED'

    for name, response in mutations.items():
        assert response.status_code == 422, name
        assert response.get_json()['error']['code'] == 'TENANT_CONTEXT_REQUIRED'
