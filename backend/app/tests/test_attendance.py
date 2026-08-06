from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import AttendanceRecord, Employee
from app.services.auth_service import register_user


PASSWORD = 'StrongPass123!'


def _login(app, email):
    test_client = app.test_client()
    response = test_client.post(
        '/api/auth/login',
        json={'email': email, 'password': PASSWORD},
    )
    assert response.status_code == 200
    csrf_cookie = test_client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None
    return test_client, {'X-CSRF-TOKEN': csrf_cookie.value}


def _create_employee(
    app,
    tenant_id,
    employee_number,
    email,
    *,
    manager_id=None,
    roles=None,
):
    with app.app_context():
        user = None
        if roles:
            user = register_user({
                'tenant_id': tenant_id,
                'email': email,
                'first_name': employee_number,
                'last_name': 'User',
                'password': PASSWORD,
                'roles': roles,
            })

        employee = Employee(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            employee_number=employee_number,
            first_name=employee_number,
            last_name='User',
            email=email,
            hire_date=date(2026, 1, 1),
            manager_id=manager_id,
        )
        db.session.add(employee)
        db.session.commit()
        return str(employee.id)


def _create_attendance(
    app,
    tenant_id,
    employee_id,
    work_date,
    *,
    completed=True,
):
    with app.app_context():
        check_in_at = datetime.combine(work_date, datetime.min.time()).replace(
            hour=8,
        )
        record = AttendanceRecord(
            tenant_id=tenant_id,
            employee_id=employee_id,
            work_date=work_date,
            check_in_at=check_in_at,
            check_out_at=(
                check_in_at + timedelta(hours=8)
                if completed else None
            ),
        )
        db.session.add(record)
        db.session.commit()
        return str(record.id)


def test_manager_attendance_totals_are_scoped_before_pagination(
    app,
    tenant,
):
    manager_employee_id = _create_employee(
        app,
        tenant.id,
        'MGR-ATT',
        'attendance-manager@acme.test',
        roles=['MANAGER'],
    )
    direct_report_id = _create_employee(
        app,
        tenant.id,
        'EMP-DIRECT-ATT',
        'direct-attendance@acme.test',
        manager_id=manager_employee_id,
    )
    unrelated_id = _create_employee(
        app,
        tenant.id,
        'EMP-OUTSIDE-ATT',
        'outside-attendance@acme.test',
    )

    start = date.today() - timedelta(days=24)
    for index in range(25):
        _create_attendance(
            app,
            tenant.id,
            direct_report_id,
            start + timedelta(days=index),
            completed=index < 20,
        )

    for index in range(10):
        _create_attendance(
            app,
            tenant.id,
            unrelated_id,
            start + timedelta(days=index),
            completed=True,
        )

    manager_client, headers = _login(
        app,
        'attendance-manager@acme.test',
    )
    list_response = manager_client.get(
        '/api/attendance',
        query_string={'page': 1, 'per_page': 10},
        headers=headers,
    )
    assert list_response.status_code == 200
    data = list_response.get_json()['data']
    assert data['meta']['total'] == 25
    assert data['meta']['pages'] == 3
    assert len(data['items']) == 10
    assert {
        item['employee_name']
        for item in data['items']
    } == {'EMP-DIRECT-ATT User'}

    summary_response = manager_client.get(
        '/api/attendance/summary',
        headers=headers,
    )
    assert summary_response.status_code == 200
    summary = summary_response.get_json()['data']
    assert summary['total'] == 25
    assert summary['completed'] == 20
    assert summary['open_sessions'] == 5
    assert summary['today_checked_in'] == 1
    assert summary['today_open'] == 1


def test_attendance_filters_and_sorting_run_on_the_server(app, tenant):
    manager_employee_id = _create_employee(
        app,
        tenant.id,
        'MGR-FILTER',
        'attendance-filter-manager@acme.test',
        roles=['MANAGER'],
    )
    direct_report_id = _create_employee(
        app,
        tenant.id,
        'EMP-FILTER',
        'filter-person@acme.test',
        manager_id=manager_employee_id,
    )

    first_date = date(2026, 7, 1)
    for index in range(6):
        _create_attendance(
            app,
            tenant.id,
            direct_report_id,
            first_date + timedelta(days=index),
            completed=index % 2 == 0,
        )

    manager_client, headers = _login(
        app,
        'attendance-filter-manager@acme.test',
    )
    response = manager_client.get(
        '/api/attendance',
        query_string={
            'q': 'EMP-FILTER',
            'status': 'complete',
            'date_from': '2026-07-01',
            'date_to': '2026-07-06',
            'sort': 'work_date',
            'direction': 'asc',
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['meta']['total'] == 3
    assert [item['work_date'] for item in data['items']] == [
        '2026-07-01',
        '2026-07-03',
        '2026-07-05',
    ]

    invalid = manager_client.get(
        '/api/attendance',
        query_string={'date_from': 'not-a-date'},
        headers=headers,
    )
    assert invalid.status_code == 422


def test_employee_can_load_and_update_today_attendance(app, tenant):
    _create_employee(
        app,
        tenant.id,
        'EMP-SELF-ATT',
        'attendance-self@acme.test',
        roles=['EMPLOYEE'],
    )
    employee_client, headers = _login(app, 'attendance-self@acme.test')

    empty = employee_client.get(
        '/api/attendance/me/today',
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.get_json()['data'] == {}

    checked_in = employee_client.post(
        '/api/attendance/check-in',
        headers=headers,
    )
    assert checked_in.status_code == 200
    assert checked_in.get_json()['data']['check_in_at'] is not None

    current = employee_client.get(
        '/api/attendance/me/today',
        headers=headers,
    )
    assert current.status_code == 200
    assert current.get_json()['data']['check_in_at'] is not None

    checked_out = employee_client.post(
        '/api/attendance/check-out',
        headers=headers,
    )
    assert checked_out.status_code == 200
    assert checked_out.get_json()['data']['check_out_at'] is not None
