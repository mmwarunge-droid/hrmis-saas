from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect as sa_inspect

from app.extensions import db
from app.models import Document, Employee, Tenant
from app.services.auth_service import register_user


PASSWORD = 'StrongPass123!'


def _login(app, email):
    test_client = app.test_client()
    response = test_client.post(
        '/api/auth/login',
        json={'email': email, 'password': PASSWORD},
    )
    assert response.status_code == 200
    csrf_cookie = test_client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None
    return test_client, {'X-CSRF-TOKEN': csrf_cookie.value}


def _create_employee(
    app,
    tenant_id,
    employee_number,
    email,
    *,
    manager_id=None,
    roles=None,
):
    with app.app_context():
        user = None
        if roles:
            user = register_user({
                'tenant_id': tenant_id,
                'email': email,
                'first_name': employee_number,
                'last_name': 'User',
                'password': PASSWORD,
                'roles': roles,
            })

        employee = Employee(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            employee_number=employee_number,
            first_name=employee_number,
            last_name='User',
            email=email,
            hire_date=date(2026, 1, 1),
            manager_id=manager_id,
        )
        db.session.add(employee)
        db.session.commit()
        return (
            str(user.id) if user else None,
            str(employee.id),
        )


def _create_document(
    app,
    tenant_id,
    uploaded_by_id,
    title,
    *,
    employee_id=None,
    access_level='employee',
):
    with app.app_context():
        upload_directory = Path(app.config['UPLOAD_FOLDER']) / str(tenant_id)
        upload_directory.mkdir(parents=True, exist_ok=True)
        stored_filename = f'{uuid4().hex}.txt'
        file_path = upload_directory / stored_filename
        file_path.write_text(title)

        document = Document(
            tenant_id=tenant_id,
            employee_id=employee_id,
            uploaded_by_id=uploaded_by_id,
            title=title,
            document_type='contract',
            original_filename=f'{title}.txt',
            stored_filename=stored_filename,
            file_path=str(file_path),
            mime_type='text/plain',
            size_bytes=file_path.stat().st_size,
            access_level=access_level,
        )
        db.session.add(document)
        db.session.commit()
        return str(document.id)


def test_manager_access_is_filtered_before_pagination(
    app,
    tenant,
    admin_user,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    admin_user_id = sa_inspect(admin_user).identity[0]
    _manager_user_id, manager_employee_id = _create_employee(
        app,
        tenant.id,
        'MGR-001',
        'manager@acme.test',
        roles=['MANAGER'],
    )
    _user_id, direct_report_id = _create_employee(
        app,
        tenant.id,
        'EMP-REPORT',
        'report@acme.test',
        manager_id=manager_employee_id,
    )
    _user_id, unrelated_employee_id = _create_employee(
        app,
        tenant.id,
        'EMP-OTHER',
        'other@acme.test',
    )

    accessible_ids = {
        _create_document(
            app,
            tenant.id,
            admin_user_id,
            'Manager own record',
            employee_id=manager_employee_id,
        ),
        _create_document(
            app,
            tenant.id,
            admin_user_id,
            'Direct report employee record',
            employee_id=direct_report_id,
            access_level='employee',
        ),
        _create_document(
            app,
            tenant.id,
            admin_user_id,
            'Direct report manager record',
            employee_id=direct_report_id,
            access_level='manager',
        ),
        _create_document(
            app,
            tenant.id,
            admin_user_id,
            'Manager shared policy',
            access_level='manager',
        ),
    }

    for index in range(25):
        _create_document(
            app,
            tenant.id,
            admin_user_id,
            f'Unrelated record {index:02d}',
            employee_id=unrelated_employee_id,
            access_level='employee',
        )

    manager_client, headers = _login(app, 'manager@acme.test')
    page_one = manager_client.get(
        '/api/documents?page=1&per_page=2',
        headers=headers,
    )
    page_two = manager_client.get(
        '/api/documents?page=2&per_page=2',
        headers=headers,
    )

    assert page_one.status_code == 200
    assert page_two.status_code == 200

    page_one_data = page_one.get_json()['data']
    page_two_data = page_two.get_json()['data']
    assert page_one_data['meta']['total'] == 4
    assert page_one_data['meta']['pages'] == 2
    assert page_two_data['meta']['total'] == 4

    returned_ids = {
        item['id']
        for item in page_one_data['items'] + page_two_data['items']
    }
    assert returned_ids == accessible_ids


def test_manager_cannot_retrieve_or_download_unrelated_document(
    app,
    tenant,
    admin_user,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    admin_user_id = sa_inspect(admin_user).identity[0]
    _manager_user_id, manager_employee_id = _create_employee(
        app,
        tenant.id,
        'MGR-002',
        'manager2@acme.test',
        roles=['MANAGER'],
    )
    _user_id, direct_report_id = _create_employee(
        app,
        tenant.id,
        'EMP-DIRECT',
        'direct@acme.test',
        manager_id=manager_employee_id,
    )
    _user_id, unrelated_employee_id = _create_employee(
        app,
        tenant.id,
        'EMP-UNRELATED',
        'unrelated@acme.test',
    )

    direct_document_id = _create_document(
        app,
        tenant.id,
        admin_user_id,
        'Direct report contract',
        employee_id=direct_report_id,
    )
    unrelated_document_id = _create_document(
        app,
        tenant.id,
        admin_user_id,
        'Unrelated contract',
        employee_id=unrelated_employee_id,
    )

    manager_client, headers = _login(app, 'manager2@acme.test')

    assert manager_client.get(
        f'/api/documents/{direct_document_id}',
        headers=headers,
    ).status_code == 200
    assert manager_client.get(
        f'/api/documents/{direct_document_id}/download',
        headers=headers,
    ).status_code == 200

    assert manager_client.get(
        f'/api/documents/{unrelated_document_id}',
        headers=headers,
    ).status_code == 403
    assert manager_client.get(
        f'/api/documents/{unrelated_document_id}/download',
        headers=headers,
    ).status_code == 403


def test_document_access_does_not_cross_tenant_boundaries(
    app,
    tenant,
    admin_user,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    admin_user_id = sa_inspect(admin_user).identity[0]
    _manager_user_id, _manager_employee_id = _create_employee(
        app,
        tenant.id,
        'MGR-003',
        'manager3@acme.test',
        roles=['MANAGER'],
    )

    with app.app_context():
        other_tenant = Tenant(
            name='Other Ltd',
            slug='other-ltd',
            country='Kenya',
        )
        db.session.add(other_tenant)
        db.session.commit()
        other_tenant_id = other_tenant.id

    _other_user_id, other_employee_id = _create_employee(
        app,
        other_tenant_id,
        'OTHER-001',
        'employee@other.test',
    )
    other_document_id = _create_document(
        app,
        other_tenant_id,
        admin_user_id,
        'Other tenant document',
        employee_id=other_employee_id,
        access_level='manager',
    )

    manager_client, headers = _login(app, 'manager3@acme.test')
    list_response = manager_client.get('/api/documents', headers=headers)

    assert list_response.status_code == 200
    assert list_response.get_json()['data']['meta']['total'] == 0
    assert manager_client.get(
        f'/api/documents/{other_document_id}',
        headers=headers,
    ).status_code == 404
