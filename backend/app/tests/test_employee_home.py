import io
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import (
    Employee,
    LeaveRequest,
    LeaveType,
    OrganizationEvent,
    Tenant,
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

    # A managed URL produced by Kinetic must be valid when the
    # homepage settings are subsequently saved.
    managed_update = client.patch(
        f'/api/tenants/{tenant.id}/homepage-settings',
        json={'logo_url': logo_url},
        headers=auth_headers,
    )
    assert managed_update.status_code == 200
    assert managed_update.get_json()['data']['logo_url'] == logo_url

    # Arbitrary relative paths must not be accepted.
    invalid_managed_path = client.patch(
        f'/api/tenants/{tenant.id}/homepage-settings',
        json={'logo_url': '/uploads/unmanaged-logo.png'},
        headers=auth_headers,
    )
    assert invalid_managed_path.status_code == 422

    # External branding must use HTTPS.
    insecure_external_url = client.patch(
        f'/api/tenants/{tenant.id}/homepage-settings',
        json={'logo_url': 'http://cdn.example.test/logo.png'},
        headers=auth_headers,
    )
    assert insecure_external_url.status_code == 422


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
            hire_date=date.today(),
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

def test_foreign_tenant_employee_link_is_not_self_profile(
    client,
    app,
    tenant,
):
    with app.app_context():
        other_tenant = Tenant(
            name='Other Organization',
            slug='other-organization',
            country='Kenya',
        )
        db.session.add(other_tenant)
        db.session.flush()

        user = register_user({
            'tenant_id': tenant.id,
            'email': 'foreign-link@acme.test',
            'first_name': 'Foreign',
            'last_name': 'Link',
            'password': 'StrongPass123!',
            'roles': ['CLIENT_ADMIN'],
        })

        foreign_employee = Employee(
            tenant_id=other_tenant.id,
            user_id=user.id,
            employee_number='OTHER-001',
            first_name='Foreign',
            last_name='Link',
            email='foreign-link@other.test',
            hire_date=date.today(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(foreign_employee)
        db.session.commit()

        foreign_employee_id = foreign_employee.id

    _login(client, 'foreign-link@acme.test')

    me = client.get('/api/auth/me')
    assert me.status_code == 200
    assert me.get_json()['data']['employee_profile'] is None

    home = client.get('/api/employee-home')
    assert home.status_code == 200
    assert 'id' not in home.get_json()['data']['viewer']

    update = client.patch(
        '/api/employee-home/profile',
        json={'biography': 'Must not cross tenant boundaries'},
        headers=_csrf_header(client),
    )

    assert update.status_code == 409
    assert update.get_json()['error']['code'] == 'EMPLOYEE_PROFILE_REQUIRED'

    upload = client.post(
        '/api/employee-home/profile-image/photo',
        data={},
        headers=_csrf_header(client),
    )
    assert upload.status_code == 409
    assert upload.get_json()['error']['code'] == 'EMPLOYEE_PROFILE_REQUIRED'

    with app.app_context():
        employee = db.session.get(Employee, foreign_employee_id)
        assert employee.biography is None


def test_soft_deleted_employee_link_is_not_self_profile(
    client,
    app,
    tenant,
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant.id,
            'email': 'deleted-profile@acme.test',
            'first_name': 'Deleted',
            'last_name': 'Profile',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        employee = Employee(
            tenant_id=tenant.id,
            user_id=user.id,
            employee_number='EMP-DELETED',
            first_name='Deleted',
            last_name='Profile',
            email='deleted-profile@acme.test',
            hire_date=date.today(),
            employment_status='inactive',
            employment_type='full_time',
        )
        employee.deleted_at = datetime.utcnow()

        db.session.add(employee)
        db.session.commit()

        employee_id = employee.id

    _login(client, 'deleted-profile@acme.test')

    me = client.get('/api/auth/me')
    assert me.status_code == 200
    assert me.get_json()['data']['employee_profile'] is None

    home = client.get('/api/employee-home')
    assert home.status_code == 200
    assert 'id' not in home.get_json()['data']['viewer']

    update = client.patch(
        '/api/employee-home/profile',
        json={'biography': 'Deleted records are not self-service profiles'},
        headers=_csrf_header(client),
    )

    assert update.status_code == 409
    assert update.get_json()['error']['code'] == 'EMPLOYEE_PROFILE_REQUIRED'

    upload = client.post(
        '/api/employee-home/profile-image/photo',
        data={},
        headers=_csrf_header(client),
    )
    assert upload.status_code == 409
    assert upload.get_json()['error']['code'] == 'EMPLOYEE_PROFILE_REQUIRED'

    with app.app_context():
        employee = db.session.get(Employee, employee_id)
        assert employee.biography is None

def test_client_admin_can_use_employee_self_profile(
    client,
    app,
    tenant,
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant.id,
            'email': 'admin-employee@acme.test',
            'first_name': 'Admin',
            'last_name': 'Employee',
            'password': 'StrongPass123!',
            'roles': ['CLIENT_ADMIN'],
        })

        employee = Employee(
            tenant_id=tenant.id,
            user_id=user.id,
            employee_number='EMP-ADMIN',
            first_name='Admin',
            last_name='Employee',
            email='admin-employee@acme.test',
            hire_date=date.today(),
            employment_status='active',
            employment_type='full_time',
            job_title='People Operations Lead',
        )
        db.session.add(employee)
        db.session.commit()

        employee_id = employee.id

    _login(client, 'admin-employee@acme.test')

    me = client.get('/api/auth/me')
    assert me.status_code == 200
    assert me.get_json()['data']['employee_profile']['id'] == str(employee_id)

    home = client.get('/api/employee-home')
    assert home.status_code == 200
    assert home.get_json()['data']['viewer']['id'] == str(employee_id)

    update = client.patch(
        '/api/employee-home/profile',
        json={'biography': 'Administrator and employee.'},
        headers=_csrf_header(client),
    )
    assert update.status_code == 200
    assert update.get_json()['data']['biography'] == (
        'Administrator and employee.'
    )
