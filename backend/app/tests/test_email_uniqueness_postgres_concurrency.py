import os
import threading
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.config import DevelopmentConfig
from app.extensions import db
from app.models import Employee, Tenant, User
from app.services import auth_service, employee_service
from app.services.auth_service import register_user
from app.services.employee_service import create_employee
from app.services.rbac_service import seed_roles_permissions


@pytest.fixture()
def postgres_email_app():
    database_url = os.getenv('HRMIS_PG_TEST_URL')
    if not database_url:
        pytest.skip('HRMIS_PG_TEST_URL is required for PostgreSQL concurrency tests')

    original_database_url = DevelopmentConfig.SQLALCHEMY_DATABASE_URI
    DevelopmentConfig.SQLALCHEMY_DATABASE_URI = database_url

    app = create_app('development')
    app.config['TESTING'] = True

    tenant_id = None
    marker = uuid4().hex

    try:
        with app.app_context():
            seed_roles_permissions()
            tenant = Tenant(
                name=f'Email Concurrency {marker}',
                slug=f'email-concurrency-{marker}',
                country='Kenya',
            )
            db.session.add(tenant)
            db.session.commit()
            tenant_id = tenant.id

        yield app, tenant_id, marker

    finally:
        if tenant_id is not None:
            with app.app_context():
                Employee.query.filter_by(tenant_id=tenant_id).delete(
                    synchronize_session=False,
                )
                User.query.filter_by(tenant_id=tenant_id).delete(
                    synchronize_session=False,
                )
                tenant = db.session.get(Tenant, tenant_id)
                if tenant is not None:
                    db.session.delete(tenant)
                db.session.commit()

        DevelopmentConfig.SQLALCHEMY_DATABASE_URI = original_database_url


def test_concurrent_user_creation_leaves_one_normalized_identity(
    postgres_email_app,
    monkeypatch,
):
    app, tenant_id, marker = postgres_email_app
    email = f'concurrent-user-{marker}@example.test'
    barrier = threading.Barrier(2)
    original_check = auth_service.ensure_user_email_available
    successes = []
    errors = []

    def synchronized_check(value):
        normalized = original_check(value)
        barrier.wait(timeout=10)
        return normalized

    monkeypatch.setattr(
        auth_service,
        'ensure_user_email_available',
        synchronized_check,
    )

    def create_identity(raw_email, first_name):
        try:
            with app.app_context():
                user = register_user({
                    'tenant_id': tenant_id,
                    'email': raw_email,
                    'first_name': first_name,
                    'last_name': 'Concurrent',
                    'password': 'StrongConcurrentIdentityPass123!',
                    'roles': ['EMPLOYEE'],
                })
                successes.append(str(user.id))
        except Exception as exc:
            errors.append(exc)
            with app.app_context():
                db.session.rollback()
        finally:
            with app.app_context():
                db.session.remove()

    workers = [
        threading.Thread(
            target=create_identity,
            args=(f'  {email.upper()}  ', 'First'),
        ),
        threading.Thread(
            target=create_identity,
            args=(email, 'Second'),
        ),
    ]

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)

    assert not any(worker.is_alive() for worker in workers)
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], IntegrityError)

    with app.app_context():
        rows = User.query.filter(
            db.func.lower(db.func.trim(User.email)) == email,
        ).all()
        assert len(rows) == 1
        assert rows[0].email == email


def test_concurrent_employee_creation_leaves_one_tenant_email(
    postgres_email_app,
    monkeypatch,
):
    app, tenant_id, marker = postgres_email_app
    email = f'concurrent-employee-{marker}@example.test'
    barrier = threading.Barrier(2)
    original_check = employee_service.ensure_employee_email_available
    successes = []
    errors = []

    def synchronized_check(*args, **kwargs):
        normalized = original_check(*args, **kwargs)
        barrier.wait(timeout=10)
        return normalized

    monkeypatch.setattr(
        employee_service,
        'ensure_employee_email_available',
        synchronized_check,
    )

    def create_profile(raw_email, number):
        try:
            with app.app_context():
                employee = create_employee(
                    {
                        'employee_number': number,
                        'first_name': 'Concurrent',
                        'last_name': 'Employee',
                        'email': raw_email,
                        'hire_date': date(2026, 9, 1),
                        'job_title': 'Analyst',
                    },
                    tenant_id,
                )
                successes.append(str(employee.id))
        except Exception as exc:
            errors.append(exc)
            with app.app_context():
                db.session.rollback()
        finally:
            with app.app_context():
                db.session.remove()

    workers = [
        threading.Thread(
            target=create_profile,
            args=(f' {email.upper()} ', 'EMAIL-RACE-1'),
        ),
        threading.Thread(
            target=create_profile,
            args=(email, 'EMAIL-RACE-2'),
        ),
    ]

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)

    assert not any(worker.is_alive() for worker in workers)
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], IntegrityError)

    with app.app_context():
        rows = Employee.query.filter(
            Employee.tenant_id == tenant_id,
            db.func.lower(db.func.trim(Employee.email)) == email,
        ).all()
        assert len(rows) == 1
        assert rows[0].email == email
