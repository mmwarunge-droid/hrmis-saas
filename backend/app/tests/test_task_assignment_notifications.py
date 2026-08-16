from datetime import date

from app.extensions import db
from app.models import (
    Employee,
    Notification,
    OnboardingTask,
    OnboardingTemplate,
    Tenant,
)
from app.services.auth_service import register_user
from app.services.onboarding_service import assign_template


def test_onboarding_assignment_sends_org_aware_bell_and_email(
    app,
    tenant,
):
    with app.app_context():
        tenant_record = db.session.get(Tenant, tenant.id)

        user = register_user({
            'tenant_id': tenant.id,
            'email': 'training.assignee@example.test',
            'first_name': 'Training',
            'last_name': 'Assignee',
            'password': 'StrongTrainingPass123!',
            'roles': ['EMPLOYEE'],
        })

        employee = Employee(
            tenant_id=tenant.id,
            user_id=user.id,
            employee_number='TRAIN-001',
            first_name='Training',
            last_name='Assignee',
            email=user.email,
            hire_date=date.today(),
        )
        template = OnboardingTemplate(
            tenant_id=tenant.id,
            name='Required employee training',
            is_active=True,
        )
        db.session.add_all([employee, template])
        db.session.flush()

        task = OnboardingTask(
            tenant_id=tenant.id,
            template_id=template.id,
            title='Workplace Safety Training',
            assignee_role='EMPLOYEE',
            due_days_after_start=3,
            required=True,
        )
        db.session.add(task)
        db.session.commit()

        app.extensions.setdefault('mail_outbox', []).clear()

        assignments = assign_template(
            employee.id,
            template.id,
            tenant.id,
        )

        assert len(assignments) == 1
        assignment = assignments[0]

        notification = Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=user.id,
            notification_type='onboarding',
        ).one()

        assert tenant_record.name in notification.title
        assert 'Workplace Safety Training' in notification.body
        assert notification.action_url == '/tasks'
        assert notification.metadata_json['assignment_id'] == str(
            assignment.id
        )

        assert len(app.extensions['mail_outbox']) == 1
        message = app.extensions['mail_outbox'][0]

        assert message['to'] == user.email
        assert tenant_record.name in message['subject']
        assert 'Workplace Safety Training' in message['text']
        assert '/tasks' in message['text']
        assert 'View task in Kinetic' in message['html']
