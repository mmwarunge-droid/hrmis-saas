from datetime import date

from app.extensions import db
from app.models import Employee
from app.services.auth_service import register_user


def test_administrator_links_existing_user_to_employee(
    app,
    client,
    tenant,
    auth_headers,
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant.id,
            'email': 'linked@acme.test',
            'first_name': 'Linked',
            'last_name': 'Person',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='EMP-LINK-01',
            first_name='Linked',
            last_name='Person',
            email='linked.employee@acme.test',
            hire_date=date(2026, 1, 2),
        )
        db.session.add(employee)
        db.session.commit()
        user_id = str(user.id)
        employee_id = str(employee.id)

    response = client.patch(
        f'/api/users/{user_id}/employee-link',
        headers=auth_headers,
        json={'employee_id': employee_id},
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['employee_profile']['id'] == employee_id

    with app.app_context():
        saved = db.session.get(Employee, employee_id)
        assert str(saved.user_id) == user_id

    options = client.get('/api/users/options', headers=auth_headers)
    assert options.status_code == 200
    linked = next(
        item
        for item in options.get_json()['data']['items']
        if item['id'] == user_id
    )
    assert linked['employee_profile']['employee_number'] == 'EMP-LINK-01'

    unlink = client.patch(
        f'/api/users/{user_id}/employee-link',
        headers=auth_headers,
        json={'employee_id': None},
    )
    assert unlink.status_code == 200
    assert unlink.get_json()['data']['employee_profile'] is None
