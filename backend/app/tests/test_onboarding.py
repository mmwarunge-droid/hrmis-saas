def test_onboarding_task_completion(client, auth_headers):
    employee = client.post('/api/employees', headers=auth_headers, json={'employee_number': 'EMP-004', 'first_name': 'New', 'last_name': 'Hire', 'email': 'new@acme.test', 'hire_date': '2026-01-01'}).get_json()['data']
    template = client.post('/api/onboarding/templates', headers=auth_headers, json={'name': 'Default Onboarding', 'tasks': [{'title': 'Read policy'}]}).get_json()['data']
    assigned = client.post('/api/onboarding/assign', headers=auth_headers, json={'employee_id': employee['id'], 'template_id': template['id']})
    assert assigned.status_code == 201
    task_id = assigned.get_json()['data']['items'][0]['id']
    done = client.patch(f'/api/onboarding/tasks/{task_id}/complete', headers=auth_headers, json={'completion_notes': 'Done'})
    assert done.status_code == 200
    assert done.get_json()['data']['status'] == 'completed'
