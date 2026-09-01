from datetime import datetime, timedelta
from io import BytesIO

from app.extensions import db
from app.models import OnboardingResource, Tenant


def _minimal_mp4(duration_seconds):
    timescale = 1000
    duration = int(duration_seconds * timescale)
    mvhd_payload = (
        b'\x00\x00\x00\x00'
        + (0).to_bytes(4, 'big')
        + (0).to_bytes(4, 'big')
        + timescale.to_bytes(4, 'big')
        + duration.to_bytes(4, 'big')
    )
    mvhd = (
        (8 + len(mvhd_payload)).to_bytes(4, 'big')
        + b'mvhd'
        + mvhd_payload
    )
    return (8 + len(mvhd)).to_bytes(4, 'big') + b'moov' + mvhd


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

def test_onboarding_video_requires_verified_watch_progress(
    client,
    app,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

    missing_duration = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(b'demo training video'), 'missing.mp4'),
        },
        content_type='multipart/form-data',
    )
    assert missing_duration.status_code == 400

    server_verified = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(_minimal_mp4(20)), 'server-verified.mp4'),
        },
        content_type='multipart/form-data',
    )
    assert server_verified.status_code == 201, server_verified.get_json()
    assert server_verified.get_json()['data']['duration_seconds'] == 20.0

    uploaded = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(b'demo training video'), 'culture.mp4'),
            'duration_seconds': '20',
        },
        content_type='multipart/form-data',
    )
    assert uploaded.status_code == 201, uploaded.get_json()
    resource = uploaded.get_json()['data']
    assert resource['resource_type'] == 'video'
    assert resource['duration_seconds'] == 20.0

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
                'assignee_role': 'CLIENT_ADMIN',
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
    assignment_id = assignment['id']
    assert assignment['task_type'] == 'video'
    assert assignment['video_progress']['completion_ready'] is False

    direct_complete = client.patch(
        f'/api/onboarding/tasks/{assignment_id}/complete',
        headers=auth_headers,
        json={'acknowledged': True},
    )
    assert direct_complete.status_code == 400
    assert 'Watch the full training video' in (
        direct_complete.get_json()['error']['message']
    )

    admin_complete = client.patch(
        f'/api/onboarding/assignments/{assignment_id}',
        headers=auth_headers,
        json={'status': 'completed'},
    )
    assert admin_complete.status_code == 400

    clock = [datetime(2026, 9, 1, 8, 0, 0)]
    monkeypatch.setattr(
        'app.services.onboarding_service.utcnow',
        lambda: clock[0],
    )

    def progress(event, position, advance=0):
        clock[0] += timedelta(seconds=advance)
        response = client.patch(
            f'/api/onboarding/tasks/{assignment_id}/video-progress',
            headers=auth_headers,
            json={
                'event': event,
                'position_seconds': position,
            },
        )
        assert response.status_code == 200, response.get_json()
        return response.get_json()['data']['video_progress']

    state = progress('start', 0)
    assert state['verified_seconds'] == 0.0

    state = progress('heartbeat', 5, advance=5)
    assert state['verified_seconds'] == 5.0

    state = progress('heartbeat', 18, advance=1)
    assert state['seek_blocked'] is True
    assert state['verified_seconds'] == 5.0
    assert state['resume_position_seconds'] == 5.0

    progress('pause', 5)
    state = progress('heartbeat', 10, advance=30)
    assert state['verified_seconds'] == 5.0
    assert state['seek_blocked'] is True

    progress('start', 5)
    state = progress('heartbeat', 10, advance=5)
    assert state['verified_seconds'] == 10.0

    state = progress('heartbeat', 15, advance=5)
    assert state['verified_seconds'] == 15.0

    state = progress('ended', 20, advance=5)
    assert state['verified_seconds'] == 20.0
    assert state['remaining_seconds'] == 0.0
    assert state['completion_ready'] is True
    assert state['completed_at'] is not None

    completed = client.patch(
        f'/api/onboarding/tasks/{assignment_id}/complete',
        headers=auth_headers,
        json={'acknowledged': True},
    )
    assert completed.status_code == 200, completed.get_json()
    data = completed.get_json()['data']
    assert data['status'] == 'completed'
    assert data['acknowledged_at'] is not None
    assert data['video_progress']['completion_ready'] is True


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


def test_training_retake_reuses_content_and_preserves_attempt_history(
    client,
    app,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

    employee = client.post(
        '/api/employees',
        headers=auth_headers,
        json={
            'employee_number': 'EMP-RETAKE-01',
            'first_name': 'Retake',
            'last_name': 'Employee',
            'email': 'retake.employee@example.com',
            'hire_date': '2026-09-01',
        },
    ).get_json()['data']

    resource_response = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(b'policy content'), 'ethics.pdf'),
        },
        content_type='multipart/form-data',
    )
    assert resource_response.status_code == 201
    resource = resource_response.get_json()['data']

    template_response = client.post(
        '/api/onboarding/templates',
        headers=auth_headers,
        json={
            'name': 'Ethics Retake Plan',
            'tasks': [{
                'title': 'Workplace ethics',
                'task_type': 'document',
                'resource_id': resource['id'],
                'assignee_role': 'CLIENT_ADMIN',
                'requires_acknowledgement': True,
                'max_attempts': 2,
            }],
        },
    )
    assert template_response.status_code == 201
    template = template_response.get_json()['data']

    assigned = client.post(
        '/api/onboarding/assign',
        headers=auth_headers,
        json={
            'employee_id': employee['id'],
            'template_id': template['id'],
        },
    )
    assert assigned.status_code == 201
    assignment = assigned.get_json()['data']['items'][0]
    assignment_id = assignment['id']
    assert assignment['current_attempt_number'] == 1
    assert assignment['attempt_limit'] == 2

    completed = client.patch(
        f'/api/onboarding/tasks/{assignment_id}/complete',
        headers=auth_headers,
        json={'acknowledged': True},
    )
    assert completed.status_code == 200

    retake = client.post(
        f'/api/onboarding/assignments/{assignment_id}/retake',
        headers=auth_headers,
        json={
            'reason': 'Annual policy refresh',
            'due_date': '2026-09-30',
        },
    )
    assert retake.status_code == 201, retake.get_json()
    data = retake.get_json()['data']
    assert data['current_attempt_number'] == 2
    assert data['attempt_limit'] == 2
    assert data['attempts_remaining'] == 0
    assert data['status'] == 'pending'
    assert data['resource']['id'] == resource['id']
    assert data['resource_viewed_at'] is None
    assert data['acknowledged_at'] is None

    history = client.get(
        f'/api/onboarding/assignments/{assignment_id}/attempts',
        headers=auth_headers,
    )
    assert history.status_code == 200
    attempts = history.get_json()['data']['items']
    assert [item['attempt_number'] for item in attempts] == [2, 1]
    assert attempts[0]['status'] == 'pending'
    assert attempts[0]['authorization_reason'] == 'Annual policy refresh'
    assert attempts[1]['status'] == 'completed'
    assert attempts[1]['passed'] is True

    exhausted = client.post(
        f'/api/onboarding/assignments/{assignment_id}/retake',
        headers=auth_headers,
        json={'reason': 'Try again'},
    )
    assert exhausted.status_code == 400
    assert 'Maximum attempts reached' in exhausted.get_json()['error']['message']

    granted = client.post(
        f'/api/onboarding/assignments/{assignment_id}/retake',
        headers=auth_headers,
        json={
            'reason': 'Connectivity issue during the previous attempt',
            'grant_additional_attempts': 1,
        },
    )
    assert granted.status_code == 201, granted.get_json()
    data = granted.get_json()['data']
    assert data['current_attempt_number'] == 3
    assert data['attempt_limit'] == 3
    assert data['additional_attempts_granted'] == 1


def test_video_retake_resets_verified_progress_without_reupload(
    client,
    app,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

    employee = client.post(
        '/api/employees',
        headers=auth_headers,
        json={
            'employee_number': 'EMP-RETAKE-02',
            'first_name': 'Video',
            'last_name': 'Retake',
            'email': 'video.retake@example.com',
            'hire_date': '2026-09-01',
        },
    ).get_json()['data']

    resource_response = client.post(
        '/api/onboarding/resources',
        headers=auth_headers,
        data={
            'file': (BytesIO(b'demo video'), 'retake.webm'),
            'duration_seconds': '10',
        },
        content_type='multipart/form-data',
    )
    assert resource_response.status_code == 201
    resource = resource_response.get_json()['data']

    template = client.post(
        '/api/onboarding/templates',
        headers=auth_headers,
        json={
            'name': 'Video Retake Plan',
            'tasks': [{
                'title': 'Compliance video',
                'task_type': 'video',
                'resource_id': resource['id'],
                'assignee_role': 'CLIENT_ADMIN',
                'max_attempts': 2,
            }],
        },
    ).get_json()['data']

    assignment = client.post(
        '/api/onboarding/assign',
        headers=auth_headers,
        json={
            'employee_id': employee['id'],
            'template_id': template['id'],
        },
    ).get_json()['data']['items'][0]

    from app.extensions import db
    from app.models import EmployeeOnboardingTask

    with client.application.app_context():
        row = db.session.get(EmployeeOnboardingTask, assignment['id'])
        row.video_verified_seconds = 6.0
        row.video_last_position_seconds = 6.0
        row.status = 'in_progress'
        db.session.commit()

    retake = client.post(
        f"/api/onboarding/assignments/{assignment['id']}/retake",
        headers=auth_headers,
        json={'reason': 'Restart verified viewing from the beginning'},
    )
    assert retake.status_code == 201, retake.get_json()
    data = retake.get_json()['data']
    assert data['current_attempt_number'] == 2
    assert data['video_verified_seconds'] == 0.0
    assert data['video_last_position_seconds'] == 0.0
    assert data['video_progress']['completion_ready'] is False
    assert data['resource']['id'] == resource['id']
