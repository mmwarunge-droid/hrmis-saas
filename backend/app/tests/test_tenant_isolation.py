def test_employee_query_is_tenant_scoped(client, app, tenant, auth_headers):
    from app.extensions import db
    from app.models import Tenant
    other = Tenant(name='Other Ltd', slug='other')
    db.session.add(other)
    db.session.commit()
    res = client.post('/api/employees', headers=auth_headers, json={'tenant_id': str(other.id), 'employee_number': 'EMP-X', 'first_name': 'Wrong', 'last_name': 'Tenant', 'email': 'wrong@other.test', 'hire_date': '2026-01-01'})
    # Client admin cannot override tenant_id; employee is created under their own tenant.
    assert res.status_code == 201
    assert res.get_json()['data']['tenant_id'] == str(tenant.id)
