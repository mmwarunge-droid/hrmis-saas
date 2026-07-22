def test_employee_crud(client, auth_headers):
    payload = {'employee_number': 'EMP-001', 'first_name': 'Jane', 'last_name': 'Doe', 'email': 'jane@acme.test', 'hire_date': '2026-01-01', 'job_title': 'HR Officer'}
    create = client.post('/api/employees', headers=auth_headers, json=payload)
    assert create.status_code == 201
    employee_id = create.get_json()['data']['id']
    list_res = client.get('/api/employees', headers=auth_headers)
    assert list_res.status_code == 200
    assert list_res.get_json()['data']['items']
    patch = client.patch(f'/api/employees/{employee_id}', headers=auth_headers, json={'job_title': 'Senior HR Officer'})
    assert patch.status_code == 200
    delete = client.delete(f'/api/employees/{employee_id}', headers=auth_headers)
    assert delete.status_code == 200
