from datetime import date
from pathlib import Path

import pytest

from app.extensions import db
from app.models import (
    AttendanceRecord,
    Document,
    Employee,
    EmployeeOnboardingTask,
    LeaveRequest,
    Tenant,
    User,
)
from app.services.auth_service import authenticate
from app.services.demo_seed_service import (
    DEMO_TENANT_SLUG,
    DemoSeedError,
    demo_id,
    demo_manifest,
    reset_demo_data,
    seed_demo_data,
)


REFERENCE_DATE = date(2026, 8, 6)
DEMO_PASSWORD = 'PresentationDemo2026!'


def test_demo_seed_is_idempotent_and_presentation_ready(app, tmp_path):
    with app.app_context():
        app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

        first = seed_demo_data(
            reference=REFERENCE_DATE,
            password=DEMO_PASSWORD,
        )
        first_counts = dict(first['counts'])
        first_tenant_id = first['tenant_id']

        second = seed_demo_data(
            reference=REFERENCE_DATE,
            password=DEMO_PASSWORD,
        )

        assert second['tenant_id'] == first_tenant_id
        assert second['counts'] == first_counts
        assert second['counts'] == {
            'attendance_records': 320,
            'departments': 7,
            'documents': 40,
            'employees': 42,
            'leave_requests': 10,
            'onboarding_assignments': 15,
            'signature_requests': 2,
            'tenants': 3,
            'users': 10,
        }

        tenant = Tenant.query.filter_by(slug=DEMO_TENANT_SLUG).one()
        assert str(tenant.id) == str(demo_id('tenant:kinetic-demo'))
        assert tenant.organization_owner.email == 'owner@kinetic.demo'
        assert tenant.leave_alternate_approver.email == 'consultant@kinetic.demo'

        manager = User.query.filter_by(email='manager@kinetic.demo').one()
        employee = User.query.filter_by(email='employee@kinetic.demo').one()
        consultant = User.query.filter_by(email='consultant@kinetic.demo').one()
        assert manager.role_names == ['MANAGER']
        assert employee.role_names == ['EMPLOYEE']
        assert consultant.role_names == ['HR_CONSULTANT']
        assert manager.employee_profile.full_name == 'Brian Mutua'
        assert employee.employee_profile.manager_id == manager.employee_profile.id

        assert authenticate('consultant@kinetic.demo', DEMO_PASSWORD).id == consultant.id
        assert authenticate('employee@kinetic.demo', DEMO_PASSWORD).id == employee.id

        assert Employee.query.filter_by(tenant_id=tenant.id).count() == 42
        assert AttendanceRecord.query.filter_by(tenant_id=tenant.id).count() == 320
        assert LeaveRequest.query.filter_by(tenant_id=tenant.id).count() == 10
        assert EmployeeOnboardingTask.query.filter_by(tenant_id=tenant.id).count() == 15

        files = Document.query.filter_by(tenant_id=tenant.id).all()
        assert len(files) == 40
        assert all(Path(document.file_path).is_file() for document in files)
        assert sum(document.signature_status == 'pending' for document in files) == 5


def test_demo_reset_removes_mutations_and_restores_baseline(app, tmp_path):
    with app.app_context():
        app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
        seed_demo_data(
            reference=REFERENCE_DATE,
            password=DEMO_PASSWORD,
        )
        tenant = Tenant.query.filter_by(slug=DEMO_TENANT_SLUG).one()
        tenant_id = tenant.id
        unrelated = Tenant(
            name='Unrelated Customer Workspace',
            slug='unrelated-customer',
            country='Kenya',
        )
        db.session.add(unrelated)
        tenant.name = 'Changed during a sales demonstration'
        db.session.add(
            Employee(
                tenant_id=tenant.id,
                employee_number='EXTRA-1',
                first_name='Temporary',
                last_name='Record',
                email='temporary.record@people.kinetic.demo',
                hire_date=REFERENCE_DATE,
                employment_status='active',
                employment_type='full_time',
            )
        )
        db.session.commit()
        assert Employee.query.filter_by(tenant_id=tenant.id).count() == 43

        result = reset_demo_data(
            reference=REFERENCE_DATE,
            password=DEMO_PASSWORD,
        )

        restored = Tenant.query.filter_by(slug=DEMO_TENANT_SLUG).one()
        assert restored.id == tenant_id
        assert restored.name == 'Kinetic Demo Group'
        assert result['counts']['employees'] == 42
        assert Employee.query.filter_by(tenant_id=restored.id).count() == 42
        assert Employee.query.filter_by(employee_number='EXTRA-1').count() == 0
        assert Tenant.query.filter_by(slug='unrelated-customer').count() == 1


def test_demo_cli_requires_reset_confirmation(app, tmp_path):
    with app.app_context():
        app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')

    runner = app.test_cli_runner()
    refused = runner.invoke(args=['demo-reset', '--as-of', '2026-08-06'])
    assert refused.exit_code != 0
    assert 'Reset not confirmed' in refused.output

    completed = runner.invoke(args=[
        'demo-reset',
        '--yes',
        '--as-of',
        '2026-08-06',
        '--password',
        DEMO_PASSWORD,
    ])
    assert completed.exit_code == 0
    assert '"employees": 42' in completed.output

    with app.app_context():
        manifest = demo_manifest(REFERENCE_DATE)
        assert manifest['seeded'] is True


def test_demo_seed_is_disabled_in_production(app):
    with app.app_context():
        app.config['ENVIRONMENT'] = 'production'
        with pytest.raises(DemoSeedError, match='disabled in production'):
            seed_demo_data(
                reference=REFERENCE_DATE,
                password=DEMO_PASSWORD,
            )
