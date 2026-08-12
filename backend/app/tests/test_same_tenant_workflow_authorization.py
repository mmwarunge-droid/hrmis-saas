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


def _seed_same_tenant_workflow_matrix(app, tenant_id):
    with app.app_context():
        manager_a = register_user({
            'tenant_id': tenant_id,
            'email': 'matrix.manager-a@acme.test',
            'first_name': 'Manager',
            'last_name': 'Alpha',
            'password': 'StrongPass123!',
            'roles': ['MANAGER'],
        })
        manager_b = register_user({
            'tenant_id': tenant_id,
            'email': 'matrix.manager-b@acme.test',
            'first_name': 'Manager',
            'last_name': 'Beta',
            'password': 'StrongPass123!',
            'roles': ['MANAGER'],
        })
        direct_user = register_user({
            'tenant_id': tenant_id,
            'email': 'matrix.direct@acme.test',
            'first_name': 'Direct',
            'last_name': 'Report',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        unrelated_user = register_user({
            'tenant_id': tenant_id,
            'email': 'matrix.unrelated@acme.test',
            'first_name': 'Unrelated',
            'last_name': 'Employee',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        manager_a_employee = Employee(
            tenant_id=tenant_id,
            user_id=manager_a.id,
            employee_number='MATRIX-MGR-A',
            first_name='Manager',
            last_name='Alpha',
            email=manager_a.email,
            hire_date=date(2025, 1, 1),
        )
        manager_b_employee = Employee(
            tenant_id=tenant_id,
            user_id=manager_b.id,
            employee_number='MATRIX-MGR-B',
            first_name='Manager',
            last_name='Beta',
            email=manager_b.email,
            hire_date=date(2025, 1, 1),
        )
        db.session.add_all([manager_a_employee, manager_b_employee])
        db.session.flush()

        direct_employee = Employee(
            tenant_id=tenant_id,
            user_id=direct_user.id,
            employee_number='MATRIX-DIRECT',
            first_name='Direct',
            last_name='Report',
            email=direct_user.email,
            hire_date=date(2025, 2, 1),
            manager_id=manager_a_employee.id,
        )
        unrelated_employee = Employee(
            tenant_id=tenant_id,
            user_id=unrelated_user.id,
            employee_number='MATRIX-UNRELATED',
            first_name='Unrelated',
            last_name='Employee',
            email=unrelated_user.email,
            hire_date=date(2025, 2, 1),
            manager_id=manager_b_employee.id,
        )
        db.session.add_all([direct_employee, unrelated_employee])
        db.session.flush()

        direct_goal = Goal(
            tenant_id=tenant_id,
            title='Direct report private goal',
            owner_type='employee',
            employee_id=direct_employee.id,
            created_by_user_id=manager_a.id,
            target_value=10,
            current_value=2,
            unit='outcomes',
            start_date=date(2026, 8, 1),
            due_date=date(2026, 12, 31),
            progress_percent=20,
        )
        unrelated_goal = Goal(
            tenant_id=tenant_id,
            title='Unrelated employee private goal',
            owner_type='employee',
            employee_id=unrelated_employee.id,
            created_by_user_id=manager_b.id,
            target_value=10,
            current_value=1,
            unit='outcomes',
            start_date=date(2026, 8, 1),
            due_date=date(2026, 12, 31),
            progress_percent=10,
        )
        db.session.add_all([direct_goal, unrelated_goal])

        direct_document = Document(
            tenant_id=tenant_id,
            employee_id=direct_employee.id,
            uploaded_by_id=manager_a.id,
            title='Direct report private document',
            document_type='contract',
            original_filename='matrix-direct.pdf',
            stored_filename='matrix-direct-private.pdf',
            file_path='/tmp/matrix-direct-private.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='a' * 64,
            access_level='employee',
            status='active',
        )
        unrelated_document = Document(
            tenant_id=tenant_id,
            employee_id=unrelated_employee.id,
            uploaded_by_id=manager_b.id,
            title='Unrelated employee private document',
            document_type='contract',
            original_filename='matrix-unrelated.pdf',
            stored_filename='matrix-unrelated-private.pdf',
            file_path='/tmp/matrix-unrelated-private.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='b' * 64,
            access_level='employee',
            status='active',
        )
        db.session.add_all([direct_document, unrelated_document])

        template = OnboardingTemplate(
            tenant_id=tenant_id,
            name='Same-tenant authorization matrix',
        )
        db.session.add(template)
        db.session.flush()

        task = OnboardingTask(
            tenant_id=tenant_id,
            template_id=template.id,
            title='Private onboarding work',
            assignee_role='EMPLOYEE',
            due_days_after_start=0,
        )
        db.session.add(task)
        db.session.flush()

        direct_assignment = EmployeeOnboardingTask(
            tenant_id=tenant_id,
            employee_id=direct_employee.id,
            task_id=task.id,
            status='pending',
            due_date=date(2026, 8, 30),
        )
        unrelated_assignment = EmployeeOnboardingTask(
            tenant_id=tenant_id,
            employee_id=unrelated_employee.id,
            task_id=task.id,
            status='pending',
            due_date=date(2026, 8, 30),
        )
        db.session.add_all([direct_assignment, unrelated_assignment])

        leave_type = LeaveType(
            tenant_id=tenant_id,
            code='MATRIX-LEAVE',
            name='Matrix Leave',
            annual_entitlement_days=20,
            requires_approval=True,
        )
        db.session.add(leave_type)
        db.session.flush()

        direct_leave = LeaveRequest(
            tenant_id=tenant_id,
            employee_id=direct_employee.id,
            leave_type_id=leave_type.id,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            total_days=2,
            reason='Direct report private leave',
            status='pending',
            requested_by_user_id=direct_user.id,
            required_approver_id=manager_a.id,
            approval_route='employee_to_manager',
        )
        unrelated_leave = LeaveRequest(
            tenant_id=tenant_id,
            employee_id=unrelated_employee.id,
            leave_type_id=leave_type.id,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 15),
            total_days=2,
            reason='Unrelated employee private leave',
            status='pending',
            requested_by_user_id=unrelated_user.id,
            required_approver_id=manager_b.id,
            approval_route='employee_to_manager',
        )
        db.session.add_all([direct_leave, unrelated_leave])
        db.session.commit()

        return {
            'manager_a_email': manager_a.email,
            'direct_email': direct_user.email,
            'direct_employee_id': str(direct_employee.id),
            'unrelated_employee_id': str(unrelated_employee.id),
            'direct_goal_id': str(direct_goal.id),
            'unrelated_goal_id': str(unrelated_goal.id),
            'direct_document_id': str(direct_document.id),
            'unrelated_document_id': str(unrelated_document.id),
            'direct_assignment_id': str(direct_assignment.id),
            'unrelated_assignment_id': str(unrelated_assignment.id),
            'direct_leave_id': str(direct_leave.id),
            'unrelated_leave_id': str(unrelated_leave.id),
        }


def test_employee_cannot_cross_peer_private_workflow_boundaries(
    app,
    client,
    tenant,
):
    seeded = _seed_same_tenant_workflow_matrix(app, tenant.id)
    headers = _login(client, seeded['direct_email'])

    goal = client.get(
        f"/api/goals/{seeded['unrelated_goal_id']}",
    )
    document = client.get(
        f"/api/documents/{seeded['unrelated_document_id']}",
    )
    job_history = client.get(
        f"/api/employees/{seeded['unrelated_employee_id']}/job-history",
    )
    onboarding = client.patch(
        '/api/onboarding/tasks/'
        f"{seeded['unrelated_assignment_id']}/complete",
        headers=headers,
        json={'completion_notes': 'Must not complete peer work'},
    )
    leave_listing = client.get('/api/leave/requests')

    assert goal.status_code == 404
    assert document.status_code == 403
    assert job_history.status_code == 403
    assert onboarding.status_code == 403
    assert leave_listing.status_code == 200
    assert seeded['unrelated_leave_id'] not in {
        item['id']
        for item in leave_listing.get_json()['data']['items']
    }


def test_manager_cannot_cross_unrelated_team_boundaries(
    app,
    client,
    tenant,
):
    seeded = _seed_same_tenant_workflow_matrix(app, tenant.id)
    headers = _login(client, seeded['manager_a_email'])

    goal = client.get(
        f"/api/goals/{seeded['unrelated_goal_id']}",
    )
    check_in = client.post(
        f"/api/goals/{seeded['unrelated_goal_id']}/check-ins",
        headers=headers,
        json={
            'current_value': 4,
            'health': 'on_track',
            'note': 'Must not update an unrelated employee goal',
        },
    )
    document = client.get(
        f"/api/documents/{seeded['unrelated_document_id']}",
    )
    job_history = client.get(
        f"/api/employees/{seeded['unrelated_employee_id']}/job-history",
    )
    onboarding = client.patch(
        '/api/onboarding/assignments/'
        f"{seeded['unrelated_assignment_id']}",
        headers=headers,
        json={
            'status': 'waived',
            'completion_notes': 'Must not administer unrelated employee work',
        },
    )
    leave_listing = client.get('/api/leave/requests')

    assert goal.status_code == 404
    assert check_in.status_code == 404
    assert document.status_code == 403
    assert job_history.status_code == 403
    assert onboarding.status_code == 403
    assert leave_listing.status_code == 200
    assert seeded['unrelated_leave_id'] not in {
        item['id']
        for item in leave_listing.get_json()['data']['items']
    }


def test_manager_retains_direct_report_workflow_scope(
    app,
    client,
    tenant,
):
    seeded = _seed_same_tenant_workflow_matrix(app, tenant.id)
    headers = _login(client, seeded['manager_a_email'])

    goal = client.get(
        f"/api/goals/{seeded['direct_goal_id']}",
    )
    check_in = client.post(
        f"/api/goals/{seeded['direct_goal_id']}/check-ins",
        headers=headers,
        json={
            'current_value': 5,
            'health': 'on_track',
            'note': 'Direct-report coaching check-in',
        },
    )
    document = client.get(
        f"/api/documents/{seeded['direct_document_id']}",
    )
    job_history = client.get(
        f"/api/employees/{seeded['direct_employee_id']}/job-history",
    )
    onboarding = client.patch(
        '/api/onboarding/assignments/'
        f"{seeded['direct_assignment_id']}",
        headers=headers,
        json={
            'status': 'waived',
            'completion_notes': 'Manager-approved direct-report exception',
        },
    )
    leave_listing = client.get('/api/leave/requests')

    assert goal.status_code == 200
    assert check_in.status_code == 201
    assert document.status_code == 200
    assert job_history.status_code == 200
    assert onboarding.status_code == 200
    assert leave_listing.status_code == 200

    leave_ids = {
        item['id']
        for item in leave_listing.get_json()['data']['items']
    }
    assert seeded['direct_leave_id'] in leave_ids
    assert seeded['unrelated_leave_id'] not in leave_ids


def test_wrong_leave_actor_is_rejected_at_authorization_boundary(
    app,
    client,
    tenant,
):
    seeded = _seed_same_tenant_workflow_matrix(app, tenant.id)

    manager_headers = _login(client, seeded['manager_a_email'])
    approve = client.patch(
        f"/api/leave/requests/{seeded['unrelated_leave_id']}/approve",
        headers=manager_headers,
        json={'decision_notes': 'Must not approve unrelated leave'},
    )
    reject = client.patch(
        f"/api/leave/requests/{seeded['unrelated_leave_id']}/reject",
        headers=manager_headers,
        json={'decision_notes': 'Must not reject unrelated leave'},
    )

    employee_headers = _login(client, seeded['direct_email'])
    cancel = client.patch(
        f"/api/leave/requests/{seeded['unrelated_leave_id']}/cancel",
        headers=employee_headers,
        json={'decision_notes': 'Must not cancel peer leave'},
    )

    responses = {
        'approve': approve,
        'reject': reject,
        'cancel': cancel,
    }
    assert {
        action: response.status_code
        for action, response in responses.items()
    } == {
        'approve': 403,
        'reject': 403,
        'cancel': 403,
    }

    for response in responses.values():
        assert response.get_json()['error']['code'] == 'FORBIDDEN'

    with app.app_context():
        leave_request = db.session.get(
            LeaveRequest,
            seeded['unrelated_leave_id'],
        )
        assert leave_request.status == 'pending'
        assert leave_request.approver_id is None
        assert leave_request.decided_at is None
