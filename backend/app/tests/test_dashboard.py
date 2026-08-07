from datetime import date, timedelta

from app.extensions import db
from app.models import Employee, LeaveRequest, LeaveType


def test_dashboard_summary_uses_aggregate_queries_beyond_first_page(
    app,
    client,
    tenant,
    auth_headers,
):
    today = date.today()

    with app.app_context():
        employees = []
        for index in range(35):
            employees.append(Employee(
                tenant_id=tenant.id,
                employee_number=f'DASH-{index:03d}',
                first_name='Dashboard',
                last_name=f'{index:02d}',
                email=f'dashboard-{index:03d}@summary.test',
                hire_date=today - timedelta(days=index),
                employment_status=(
                    'active'
                    if index < 28
                    else 'probation'
                ),
                job_title='Demo employee',
            ))

        db.session.add_all(employees)
        db.session.flush()

        leave_type = LeaveType(
            tenant_id=tenant.id,
            code='ANNUAL-DASH',
            name='Dashboard annual leave',
            annual_entitlement_days=21,
        )
        db.session.add(leave_type)
        db.session.flush()

        pending_requests = [
            LeaveRequest(
                tenant_id=tenant.id,
                employee_id=employees[index % len(employees)].id,
                leave_type_id=leave_type.id,
                start_date=today + timedelta(days=index + 1),
                end_date=today + timedelta(days=index + 1),
                total_days=1,
                status='pending',
            )
            for index in range(27)
        ]
        approved_requests = [
            LeaveRequest(
                tenant_id=tenant.id,
                employee_id=employees[index].id,
                leave_type_id=leave_type.id,
                start_date=today + timedelta(days=index + 1),
                end_date=today + timedelta(days=index + 2),
                total_days=2,
                status='approved',
            )
            for index in range(8)
        ]
        past_request = LeaveRequest(
            tenant_id=tenant.id,
            employee_id=employees[-1].id,
            leave_type_id=leave_type.id,
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=8),
            total_days=3,
            status='approved',
        )

        db.session.add_all([
            *pending_requests,
            *approved_requests,
            past_request,
        ])
        db.session.commit()

    response = client.get('/api/dashboard/summary', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['employees'] == 35
    assert data['active_employees'] == 28
    assert data['inactive_employees'] == 7
    assert data['people_health_percent'] == 80
    assert data['pending_leave_requests'] == 27

    assert len(data['recent_hires']) == 5
    assert [item['full_name'] for item in data['recent_hires']] == [
        'Dashboard 00',
        'Dashboard 01',
        'Dashboard 02',
        'Dashboard 03',
        'Dashboard 04',
    ]

    assert len(data['upcoming_leave']) == 5
    assert [item['employee_name'] for item in data['upcoming_leave']] == [
        'Dashboard 00',
        'Dashboard 01',
        'Dashboard 02',
        'Dashboard 03',
        'Dashboard 04',
    ]
    assert all(
        item['employee_profile_photo_url'] is None
        for item in data['upcoming_leave']
    )
