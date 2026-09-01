from io import BytesIO

from app.extensions import db
from app.models import OnboardingResource, Tenant


def test_onboarding_task_completion(client, auth_headers):
    employee = client.post('/api/employees', headers=auth_headers, json={'employee_number': 'EMP-004', 'first_name': 'New', 'last_name': 'Hire', 'email': 'new@acme.test', 'hire_date': '2026-01-01'}).get_json()['data']
    template = client.post('/api/onboarding/templates', headers=auth_headers, json={'name': 'Default Onboarding', 'tasks': [{'title': 'Read policy'}]}).get_json()['data']
    assigned = client.post('/api/onboarding/assign', headers=auth_headers, json={'employee_id': employee['id'], 'template_id': template['id']})
    assert assigned.status_code == 201
    task_id = assigned.get_json()['data']['items'][0]['id']
    done = client.patch(f'/api/onboarding/tasks/{task_id}/complete', headers=auth_headers, json={'completion_notes': 'Done'})
    assert done.status_code == 200
    assert done.get_json()['data']['status'] == 'completed'


def test_onboarding_administration_summary_and_assignment(client, auth_headers):
    employee = client.post(
        '/api/employees',
        headers=auth_headers,
        json={
            'employee_number': 'EMP-ADMIN-01',
            'first_name': 'Administered',
            'last_name': 'Hire',
            'email': 'administered@acme.test',
            'hire_date': '2026-08-01',
        },
    ).get_json()['data']
    template = client.post(
        '/api/onboarding/templates',
        headers=auth_headers,
        json={
            'name': 'First Week Plan',
            'description': 'A deterministic onboarding plan.',
            'tasks': [
                {
                    'title': 'Complete profile',
                    'assignee_role': 'EMPLOYEE',
                    'due_days_after_start': 1,
                },
                {
                    'title': 'Manager welcome',
                    'assignee_role': 'MANAGER',
                    'due_days_after_start': 2,
                },
            ],
        },
    ).get_json()['data']

    assigned = client.post(
        '/api/onboarding/assign',
        headers=auth_headers,
        json={
            'employee_id': employee['id'],
            'template_id': template['id'],
        },
    )
    assert assigned.status_code == 201
    items = assigned.get_json()['data']['items']
    assert len(items) == 2
    assert {item['task_title'] for item in items} == {
        'Complete profile',
        'Manager welcome',
    }

    summary = client.get('/api/onboarding/summary', headers=auth_headers)
    assert summary.status_code == 200
    assert summary.get_json()['data']['total'] == 2

    listing = client.get(
        '/api/onboarding/assignments?per_page=1',
        headers=auth_headers,
    )
    assert listing.status_code == 200
    assert listing.get_json()['data']['meta']['total'] == 2
    assignment = listing.get_json()['data']['items'][0]

    updated = client.patch(
        f"/api/onboarding/assignments/{assignment['id']}",
        headers=auth_headers,
        json={'status': 'waived', 'completion_notes': 'Not required'},
    )
    assert updated.status_code == 200
    assert updated.get_json()['data']['status'] == 'waived'

def test_onboarding_training_resource_acknowledgement(
    client,
    app,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

    uploaded = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(b'demo training video'), 'culture.mp4'),
        },
        content_type='multipart/form-data',
    )
    assert uploaded.status_code == 201, uploaded.get_json()
    resource = uploaded.get_json()['data']
    assert resource['resource_type'] == 'video'

    employee = client.post(
        '/api/employees',
        headers=auth_headers,
        json={
            'employee_number': 'EMP-TRAIN-01',
            'first_name': 'Training',
            'last_name': 'Employee',
            'email': 'training.employee@acme.test',
            'hire_date': '2026-09-01',
        },
    ).get_json()['data']

    template_response = client.post(
        '/api/onboarding/templates',
        headers=auth_headers,
        json={
            'name': 'Compliance training',
            'tasks': [{
                'title': 'Culture and AML training',
                'task_type': 'video',
                'resource_id': resource['id'],
                'requires_acknowledgement': True,
                'due_days_after_start': 3,
            }],
        },
    )
    assert template_response.status_code == 201, template_response.get_json()
    template = template_response.get_json()['data']

    assigned = client.post(
        '/api/onboarding/assign',
        headers=auth_headers,
        json={
            'employee_id': employee['id'],
            'template_id': template['id'],
        },
    )
    assert assigned.status_code == 201, assigned.get_json()
    assignment = assigned.get_json()['data']['items'][0]
    assert assignment['task_type'] == 'video'
    assert assignment['resource']['id'] == resource['id']

    content = client.get(
        f"/api/onboarding/resources/{resource['id']}/content",
        headers=auth_headers,
    )
    assert content.status_code == 200

    missing_ack = client.patch(
        f"/api/onboarding/tasks/{assignment['id']}/complete",
        headers=auth_headers,
        json={},
    )
    assert missing_ack.status_code == 400

    viewed = client.patch(
        f"/api/onboarding/tasks/{assignment['id']}/view",
        headers=auth_headers,
    )
    assert viewed.status_code == 200
    assert viewed.get_json()['data']['resource_viewed_at'] is not None

    completed = client.patch(
        f"/api/onboarding/tasks/{assignment['id']}/complete",
        headers=auth_headers,
        json={'acknowledged': True},
    )
    assert completed.status_code == 200
    assert completed.get_json()['data']['status'] == 'completed'
    assert completed.get_json()['data']['acknowledged_at'] is not None


def test_onboarding_template_rejects_cross_tenant_training_resource(
    client,
    app,
    auth_headers,
):
    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Training Org',
            slug='foreign-training-org',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()
        foreign_resource = OnboardingResource(
            tenant_id=foreign_tenant.id,
            resource_type='document',
            original_filename='foreign.pdf',
            stored_filename='foreign-training-resource.pdf',
            file_path='/tmp/foreign-training-resource.pdf',
            mime_type='application/pdf',
            size_bytes=12,
        )
        db.session.add(foreign_resource)
        db.session.commit()
        foreign_resource_id = str(foreign_resource.id)

    response = client.post(
        '/api/onboarding/templates',
        headers=auth_headers,
        json={
            'name': 'Unsafe cross tenant plan',
            'tasks': [{
                'title': 'Foreign policy',
                'task_type': 'document',
                'resource_id': foreign_resource_id,
                'requires_acknowledgement': True,
            }],
        },
    )

    assert response.status_code == 400
    assert 'invalid for this organization' in (
        response.get_json()['error']['message']
    )
