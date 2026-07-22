def test_leave_approval_flow(client, auth_headers):
    employee = client.post('/api/employees', headers=auth_headers, json={'employee_number': 'EMP-003', 'first_name': 'Leave', 'last_name': 'User', 'email': 'leave@acme.test', 'hire_date': '2026-01-01'}).get_json()['data']
    leave_type = client.post('/api/leave/types', headers=auth_headers, json={'name': 'Annual Leave', 'annual_entitlement_days': '21'}).get_json()['data']
    req = client.post('/api/leave/requests', headers=auth_headers, json={'employee_id': employee['id'], 'leave_type_id': leave_type['id'], 'start_date': '2026-06-01', 'end_date': '2026-06-05', 'total_days': '5', 'reason': 'Rest'})
    assert req.status_code == 201
    approve = client.patch(f"/api/leave/requests/{req.get_json()['data']['id']}/approve", headers=auth_headers, json={'decision_notes': 'Approved'})
    assert approve.status_code == 200
    assert approve.get_json()['data']['status'] == 'approved'
