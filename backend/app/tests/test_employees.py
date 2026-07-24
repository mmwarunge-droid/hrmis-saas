def _create_employee(client, auth_headers, **overrides):
    payload = {
        'employee_number': overrides.pop('employee_number', 'EMP-001'),
        'first_name': overrides.pop('first_name', 'Jane'),
        'last_name': overrides.pop('last_name', 'Doe'),
        'email': overrides.pop('email', 'jane@acme.test'),
        'hire_date': overrides.pop('hire_date', '2026-01-01'),
        'job_title': overrides.pop('job_title', 'HR Officer'),
        **overrides,
    }
    response = client.post('/api/employees', headers=auth_headers, json=payload)
    assert response.status_code == 201
    return response.get_json()['data']


def test_employee_crud(client, auth_headers):
    employee = _create_employee(client, auth_headers)
    employee_id = employee['id']

    list_res = client.get('/api/employees', headers=auth_headers)
    assert list_res.status_code == 200
    assert list_res.get_json()['data']['items']

    patch = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'job_title': 'Senior HR Officer'},
    )
    assert patch.status_code == 200

    delete = client.delete(f'/api/employees/{employee_id}', headers=auth_headers)
    assert delete.status_code == 200


def test_employee_options_return_manager_candidates(client, auth_headers):
    leader = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-LEAD',
        first_name='Amina',
        last_name='Otieno',
        email='amina@acme.test',
        job_title='Chief People Officer',
    )

    response = client.get('/api/employees/options', headers=auth_headers)

    assert response.status_code == 200
    options = response.get_json()['data']['items']
    option = next(item for item in options if item['id'] == leader['id'])
    assert option['full_name'] == 'Amina Otieno'
    assert option['job_title'] == 'Chief People Officer'


def test_org_chart_returns_nested_reporting_hierarchy(client, auth_headers):
    leader = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-LEAD',
        first_name='Amina',
        last_name='Otieno',
        email='amina@acme.test',
        job_title='Chief People Officer',
    )
    manager = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-MGR',
        first_name='Brian',
        last_name='Kimani',
        email='brian@acme.test',
        job_title='People Operations Manager',
        manager_id=leader['id'],
    )
    report = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-RPT',
        first_name='Carol',
        last_name='Njeri',
        email='carol@acme.test',
        job_title='People Operations Analyst',
        manager_id=manager['id'],
    )

    response = client.get('/api/employees/org-chart', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()['data']
    root = next(item for item in data['roots'] if item['id'] == leader['id'])
    first_level = next(item for item in root['children'] if item['id'] == manager['id'])
    second_level = next(item for item in first_level['children'] if item['id'] == report['id'])

    assert root['direct_report_count'] == 1
    assert first_level['manager_id'] == leader['id']
    assert second_level['manager_id'] == manager['id']
    assert data['meta']['total'] == 3
    assert data['meta']['manager_count'] == 2
    assert data['meta']['max_depth'] == 3


def test_employee_cannot_report_to_self_or_create_cycle(client, auth_headers):
    leader = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-LEAD',
        first_name='Amina',
        last_name='Otieno',
        email='amina@acme.test',
    )
    report = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-RPT',
        first_name='Brian',
        last_name='Kimani',
        email='brian@acme.test',
        manager_id=leader['id'],
    )

    self_manager = client.patch(
        f"/api/employees/{report['id']}",
        headers=auth_headers,
        json={'manager_id': report['id']},
    )
    assert self_manager.status_code == 400
    assert 'themselves' in self_manager.get_json()['error']['message']

    cycle = client.patch(
        f"/api/employees/{leader['id']}",
        headers=auth_headers,
        json={'manager_id': report['id']},
    )
    assert cycle.status_code == 400
    assert 'cycle' in cycle.get_json()['error']['message']
