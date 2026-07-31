import io
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import (
    Employee,
    LeaveRequest,
    LeaveType,
    OrganizationEvent,
)
from app.services.auth_service import register_user


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _login(client, email, password='StrongPass123!'):
    response = client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    return response


def test_employee_home_is_personal_private_and_people_centred(
    client,
    app,
    tenant,
):
    today = date.today()
    with app.app_context():
        employee_user = register_user({
            'tenant_id': tenant.id,
            'email': 'employee@acme.test',
            'first_name': 'Amina',
            'last_name': 'Otieno',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant.id,
            user_id=employee_user.id,
            employee_number='EMP-001',
            first_name='Amina',
            last_name='Otieno',
            email='employee@acme.test',
            date_of_birth=date(1990, today.month, today.day),
            birthday_visibility='colleagues',
            hire_date=date(today.year - 2, today.month, today.day),
            employment_status='active',
            employment_type='full_time',
            job_title='Operations Analyst',
            work_location='Nairobi',
            hobbies_json=['Hiking'],
        )
        colleague = Employee(
            tenant_id=tenant.id,
            employee_number='EMP-002',
            first_name='Brian',
            last_name='Kamau',
            email='brian@acme.test',
            date_of_birth=date(1992, today.month, today.day),
            birthday_visibility='colleagues',
            hire_date=today - timedelta(days=5),
            employment_status='active',
            employment_type='full_time',
            job_title='Designer',
            work_location='Nairobi',
        )
        leave_type = LeaveType(
            tenant_id=tenant.id,
            name='Medical leave',
            code='MEDICAL',
            annual_entitlement_days=0,
            accrual_method='none',
            entitlement_mode='event_based',
        )
        db.session.add_all([employee, colleague, leave_type])
        db.session.flush()
        db.session.add(LeaveRequest(
            tenant_id=tenant.id,
            employee_id=colleague.id,
            leave_type_id=leave_type.id,
            start_date=today,
            end_date=today + timedelta(days=1),
            total_days=2,
            reason='Private medical details must not be exposed',
            status='approved',
        ))
        db.session.add(OrganizationEvent(
            tenant_id=tenant.id,
            title='Company all-hands',
            description='Quarterly update',
            starts_at=datetime.combine(today, datetime.min.time()) + timedelta(hours=10),
            status='published',
            audience='all',
        ))
        db.session.commit()

    _login(client, 'employee@acme.test')
    response = client.get('/api/employee-home')

    assert response.status_code == 200
    payload = response.get_json()['data']
    assert payload['viewer']['date_of_birth'] == date(1990, today.month, today.day).isoformat()
    assert any(item['full_name'] == 'Brian Kamau' for item in payload['birthdays'])
    assert all('date_of_birth' not in item for item in payload['birthdays'])
    assert payload['people_out_today'][0]['availability_label'] == 'Out today'
    assert 'reason' not in payload['people_out_today'][0]
    assert payload['events_this_week'][0]['title'] == 'Company all-hands'
    assert payload['new_hires'][0]['full_name'] == 'Brian Kamau'
    assert any(item['years'] == 2 for item in payload['anniversaries'])

    update = client.patch(
        '/api/employee-home/profile',
        json={
            'biography': 'I help teams improve operations.',
            'hobbies': ['Cycling', 'Hiking', 'Cycling'],
            'birthday_visibility': 'hr_only',
        },
        headers=_csrf_header(client),
    )
    assert update.status_code == 200
    assert update.get_json()['data']['hobbies'] == ['Cycling', 'Hiking']


def test_client_admin_manages_homepage_settings(
    client,
    app,
    tenant,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    response = client.patch(
        f'/api/tenants/{tenant.id}/homepage-settings',
        json={
            'banner_url': 'https://cdn.example.test/banner.jpg',
            'logo_url': 'https://cdn.example.test/logo.png',
            'welcome_message': 'Welcome to Acme.',
            'enabled_sections': ['essentials', 'events_this_week'],
            'section_order': ['events_this_week', 'essentials'],
            'assistant_enabled': True,
            'assistant_url': 'https://assistant.example.test',
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    settings = response.get_json()['data']
    assert settings['welcome_message'] == 'Welcome to Acme.'
    assert settings['section_order'][:2] == ['events_this_week', 'essentials']
    assert settings['assistant_enabled'] is True

    invalid = client.patch(
        f'/api/tenants/{tenant.id}/homepage-settings',
        json={'assistant_url': None},
        headers=auth_headers,
    )
    assert invalid.status_code == 422


    image = b'\x89PNG\r\n\x1a\n' + (b'branding' * 8)
    upload = client.post(
        f'/api/tenants/{tenant.id}/homepage-branding/logo',
        data={'file': (io.BytesIO(image), 'logo.png')},
        content_type='multipart/form-data',
        headers=auth_headers,
    )
    assert upload.status_code == 200
    logo_url = upload.get_json()['data']['logo_url']
    assert f'/employee-home/branding/{tenant.id}/logo-' in logo_url

    asset = client.get(logo_url)
    assert asset.status_code == 200
    assert asset.data == image


def test_employee_uploads_own_profile_image(
    client,
    app,
    tenant,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    with app.app_context():
        employee_user = register_user({
            'tenant_id': tenant.id,
            'email': 'profile-upload@acme.test',
            'first_name': 'Nia',
            'last_name': 'Wambui',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        employee = Employee(
            tenant_id=tenant.id,
            user_id=employee_user.id,
            employee_number='EMP-UPLOAD',
            first_name='Nia',
            last_name='Wambui',
            email='profile-upload@acme.test',
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(employee)
        db.session.commit()

    _login(client, 'profile-upload@acme.test')
    image = b'\x89PNG\r\n\x1a\n' + (b'profile' * 8)
    upload = client.post(
        '/api/employee-home/profile-image/photo',
        data={'file': (io.BytesIO(image), 'profile.png')},
        content_type='multipart/form-data',
        headers=_csrf_header(client),
    )

    assert upload.status_code == 200
    profile = upload.get_json()['data']
    assert '/employee-home/profile-images/' in profile['profile_photo_url']

    asset = client.get(profile['profile_photo_url'])
    assert asset.status_code == 200
    assert asset.data == image
