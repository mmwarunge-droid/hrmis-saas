from datetime import date

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


def _create_department(client, auth_headers, name, code=None, **overrides):
    response = client.post(
        '/api/employees/departments',
        headers=auth_headers,
        json={'name': name, 'code': code, **overrides},
    )
    assert response.status_code == 201
    return response.get_json()['data']


def test_department_management_assigns_head_and_tracks_counts(client, auth_headers):
    leader = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-HEAD',
        first_name='Amina',
        last_name='Otieno',
        email='amina.head@acme.test',
        job_title='Finance Director',
    )
    finance = _create_department(client, auth_headers, 'Finance', 'FIN')

    update = client.patch(
        f"/api/employees/departments/{finance['id']}",
        headers=auth_headers,
        json={'name': 'Finance & Treasury', 'head_employee_id': leader['id']},
    )

    assert update.status_code == 200
    updated = update.get_json()['data']
    assert updated['name'] == 'Finance & Treasury'
    assert updated['head_employee_id'] == leader['id']

    employee = client.get(f"/api/employees/{leader['id']}", headers=auth_headers)
    assert employee.get_json()['data']['department_id'] == finance['id']

    departments = client.get('/api/employees/departments', headers=auth_headers)
    item = next(
        entry
        for entry in departments.get_json()['data']['items']
        if entry['id'] == finance['id']
    )
    assert item['head_name'] == 'Amina Otieno'
    assert item['employee_count'] == 1


def test_bulk_department_transfer_records_job_history(client, auth_headers):
    operations = _create_department(client, auth_headers, 'Operations', 'OPS')
    first = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-101',
        first_name='Brian',
        last_name='Kimani',
        email='brian.transfer@acme.test',
        department_id=operations['id'],
    )
    second = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-102',
        first_name='Carol',
        last_name='Njeri',
        email='carol.transfer@acme.test',
        department_id=operations['id'],
    )
    strategy = _create_department(client, auth_headers, 'Strategy', 'STR')
    head_assignment = client.patch(
        f"/api/employees/departments/{operations['id']}",
        headers=auth_headers,
        json={'head_employee_id': first['id']},
    )
    assert head_assignment.status_code == 200

    response = client.post(
        '/api/employees/bulk-department-transfer',
        headers=auth_headers,
        json={
            'employee_ids': [first['id'], second['id']],
            'department_id': strategy['id'],
            'effective_date': date.today().isoformat(),
            'reason': 'Operating model restructure',
        },
    )

    assert response.status_code == 200
    assert response.get_json()['data']['updated_count'] == 2

    for employee_id in (first['id'], second['id']):
        employee = client.get(f'/api/employees/{employee_id}', headers=auth_headers)
        assert employee.get_json()['data']['department_id'] == strategy['id']

        history = client.get(
            f'/api/employees/{employee_id}/job-history',
            headers=auth_headers,
        )
        current = history.get_json()['data']['items'][0]
        assert current['department_id'] == strategy['id']
        assert current['reason'] == 'Operating model restructure'

    department_response = client.get('/api/employees/departments', headers=auth_headers)
    operations_after = next(
        item
        for item in department_response.get_json()['data']['items']
        if item['id'] == operations['id']
    )
    assert operations_after['head_employee_id'] is None


def test_archiving_department_requires_and_applies_reassignment(client, auth_headers):
    legacy = _create_department(client, auth_headers, 'Legacy Sales', 'LS')
    growth = _create_department(client, auth_headers, 'Growth', 'GRO')
    employee = _create_employee(
        client,
        auth_headers,
        employee_number='EMP-201',
        first_name='David',
        last_name='Mwangi',
        email='david.archive@acme.test',
        department_id=legacy['id'],
    )

    missing_reassignment = client.post(
        f"/api/employees/departments/{legacy['id']}/archive",
        headers=auth_headers,
        json={'reason': 'Department consolidation'},
    )
    assert missing_reassignment.status_code == 400
    assert 'replacement department' in missing_reassignment.get_json()['error']['message'].lower()

    archived = client.post(
        f"/api/employees/departments/{legacy['id']}/archive",
        headers=auth_headers,
        json={
            'replacement_department_id': growth['id'],
            'effective_date': date.today().isoformat(),
            'reason': 'Department consolidation',
        },
    )
    assert archived.status_code == 200
    assert archived.get_json()['data']['employees_reassigned'] == 1

    moved = client.get(f"/api/employees/{employee['id']}", headers=auth_headers)
    assert moved.get_json()['data']['department_id'] == growth['id']

    active_departments = client.get('/api/employees/departments', headers=auth_headers)
    assert legacy['id'] not in {
        item['id'] for item in active_departments.get_json()['data']['items']
    }

    all_departments = client.get(
        '/api/employees/departments?include_archived=true',
        headers=auth_headers,
    )
    archived_item = next(
        item
        for item in all_departments.get_json()['data']['items']
        if item['id'] == legacy['id']
    )
    assert archived_item['archived'] is True

    restored = client.post(
        f"/api/employees/departments/{legacy['id']}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200
    assert restored.get_json()['data']['archived'] is False


def test_department_parent_cycle_is_rejected(client, auth_headers):
    parent = _create_department(client, auth_headers, 'Corporate Services', 'CORP')
    child = _create_department(
        client,
        auth_headers,
        'People Operations',
        'PEO',
        parent_department_id=parent['id'],
    )

    response = client.patch(
        f"/api/employees/departments/{parent['id']}",
        headers=auth_headers,
        json={'parent_department_id': child['id']},
    )

    assert response.status_code == 400
    assert 'cycle' in response.get_json()['error']['message'].lower()
