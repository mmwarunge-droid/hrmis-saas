from datetime import date, timedelta

from app.extensions import db
from app.models import Department, Employee, Goal
from app.services.auth_service import register_user


def _csrf_headers(client, email, password='StrongPass123!'):
    response = client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    csrf = client.get_cookie('csrf_access_token')
    assert csrf is not None
    return {'X-CSRF-TOKEN': csrf.value}


def test_goal_directory_summary_filters_and_pagination(
    app,
    client,
    tenant,
    auth_headers,
):
    with app.app_context():
        department = Department(
            tenant_id=tenant.id,
            name='Growth',
            code='GROWTH',
        )
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='EMP-GOAL-01',
            first_name='Goal',
            last_name='Owner',
            email='goal.owner@acme.test',
            hire_date=date(2025, 1, 6),
            department=department,
        )
        db.session.add_all([department, employee])
        db.session.commit()
        employee_id = str(employee.id)
        department_id = str(department.id)

    for index in range(22):
        response = client.post(
            '/api/goals',
            headers=auth_headers,
            json={
                'title': f'Quarterly goal {index + 1:02d}',
                'description': 'Deterministic KPI coverage',
                'owner_type': 'employee' if index % 2 else 'department',
                'employee_id': employee_id if index % 2 else None,
                'department_id': department_id if index % 2 == 0 else None,
                'target_value': 100,
                'current_value': index,
                'unit': '%',
                'start_date': '2026-07-01',
                'due_date': '2026-09-30',
            },
        )
        assert response.status_code == 201

    summary = client.get('/api/goals/summary', headers=auth_headers)
    assert summary.status_code == 200
    assert summary.get_json()['data']['total'] == 22
    assert summary.get_json()['data']['active'] == 22

    page_two = client.get(
        '/api/goals?page=2&per_page=15&sort=title&direction=asc',
        headers=auth_headers,
    )
    assert page_two.status_code == 200
    payload = page_two.get_json()['data']
    assert payload['meta']['total'] == 22
    assert len(payload['items']) == 7

    filtered = client.get(
        '/api/goals?owner_type=department&q=quarterly',
        headers=auth_headers,
    )
    assert filtered.status_code == 200
    assert filtered.get_json()['data']['meta']['total'] == 11


def test_employee_goal_scope_and_check_in(app, client, tenant, admin_user):
    with app.app_context():
        admin_user_id = db.session.merge(admin_user).id
        employee_user = register_user({
            'tenant_id': tenant.id,
            'email': 'employee.goal@acme.test',
            'first_name': 'Employee',
            'last_name': 'Goal',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        other_user = register_user({
            'tenant_id': tenant.id,
            'email': 'other.goal@acme.test',
            'first_name': 'Other',
            'last_name': 'Goal',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant.id,
            user_id=employee_user.id,
            employee_number='EMP-GOAL-02',
            first_name='Employee',
            last_name='Goal',
            email='employee.goal.profile@acme.test',
            hire_date=date(2025, 2, 1),
        )
        other = Employee(
            tenant_id=tenant.id,
            user_id=other_user.id,
            employee_number='EMP-GOAL-03',
            first_name='Other',
            last_name='Goal',
            email='other.goal.profile@acme.test',
            hire_date=date(2025, 2, 2),
        )
        db.session.add_all([employee, other])
        db.session.flush()
        goals = [
            Goal(
                tenant_id=tenant.id,
                title='Organization health objective',
                owner_type='organization',
                target_value=100,
                current_value=50,
                unit='%',
                start_date=date.today() - timedelta(days=10),
                due_date=date.today() + timedelta(days=40),
                progress_percent=50,
                created_by_user_id=admin_user_id,
            ),
            Goal(
                tenant_id=tenant.id,
                title='My customer outcome',
                owner_type='employee',
                employee_id=employee.id,
                target_value=10,
                current_value=3,
                unit='outcomes',
                start_date=date.today() - timedelta(days=10),
                due_date=date.today() + timedelta(days=40),
                progress_percent=30,
                created_by_user_id=admin_user_id,
            ),
            Goal(
                tenant_id=tenant.id,
                title='Private goal for another employee',
                owner_type='employee',
                employee_id=other.id,
                target_value=10,
                current_value=1,
                unit='outcomes',
                start_date=date.today() - timedelta(days=10),
                due_date=date.today() + timedelta(days=40),
                progress_percent=10,
                created_by_user_id=admin_user_id,
            ),
        ]
        db.session.add_all(goals)
        db.session.commit()
        own_goal_id = str(goals[1].id)

    headers = _csrf_headers(client, 'employee.goal@acme.test')
    listing = client.get('/api/goals', headers=headers)
    assert listing.status_code == 200
    titles = {item['title'] for item in listing.get_json()['data']['items']}
    assert titles == {'Organization health objective', 'My customer outcome'}

    check_in = client.post(
        f'/api/goals/{own_goal_id}/check-ins',
        headers=headers,
        json={
            'current_value': 6,
            'health': 'on_track',
            'note': 'Customer validation completed.',
        },
    )
    assert check_in.status_code == 201
    data = check_in.get_json()['data']
    assert data['goal']['progress_percent'] == 60.0
    assert data['check_in']['note'] == 'Customer validation completed.'


def test_employee_can_create_personal_goal(app, client, tenant):
    with app.app_context():
        employee_user = register_user({
            'tenant_id': tenant.id,
            'email': 'self.goal@acme.test',
            'first_name': 'Self',
            'last_name': 'Goal',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant.id,
            user_id=employee_user.id,
            employee_number='EMP-SELF-GOAL',
            first_name='Self',
            last_name='Goal',
            email='self.goal.profile@acme.test',
            hire_date=date.today(),
        )
        db.session.add(employee)
        db.session.commit()
        employee_id = str(employee.id)

    headers = _csrf_headers(client, 'self.goal@acme.test')
    response = client.post(
        '/api/goals',
        headers=headers,
        json={
            'title': 'Improve customer response time',
            'description': 'Personal KPI for the quarter.',
            'owner_type': 'employee',
            'employee_id': employee_id,
            'target_value': 4,
            'current_value': 0,
            'unit': 'hours',
            'start_date': date.today().isoformat(),
            'due_date': (date.today() + timedelta(days=90)).isoformat(),
            'status': 'active',
        },
    )
    assert response.status_code == 201
    assert response.get_json()['data']['employee_id'] == employee_id


def test_employee_cannot_create_goal_for_another_employee(app, client, tenant):
    with app.app_context():
        actor = register_user({
            'tenant_id': tenant.id,
            'email': 'self.goal.denied@acme.test',
            'first_name': 'Self',
            'last_name': 'Denied',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        other_user = register_user({
            'tenant_id': tenant.id,
            'email': 'other.goal.denied@acme.test',
            'first_name': 'Other',
            'last_name': 'Denied',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        actor_employee = Employee(
            tenant_id=tenant.id,
            user_id=actor.id,
            employee_number='EMP-GOAL-DENY-1',
            first_name='Self',
            last_name='Denied',
            email='self.goal.denied.profile@acme.test',
            hire_date=date.today(),
        )
        other_employee = Employee(
            tenant_id=tenant.id,
            user_id=other_user.id,
            employee_number='EMP-GOAL-DENY-2',
            first_name='Other',
            last_name='Denied',
            email='other.goal.denied.profile@acme.test',
            hire_date=date.today(),
        )
        db.session.add_all([actor_employee, other_employee])
        db.session.commit()
        other_id = str(other_employee.id)

    headers = _csrf_headers(client, 'self.goal.denied@acme.test')
    response = client.post(
        '/api/goals',
        headers=headers,
        json={
            'title': 'Unauthorized goal',
            'owner_type': 'employee',
            'employee_id': other_id,
            'target_value': 10,
            'unit': 'items',
            'start_date': date.today().isoformat(),
            'due_date': (date.today() + timedelta(days=30)).isoformat(),
            'status': 'active',
        },
    )
    assert response.status_code == 403
