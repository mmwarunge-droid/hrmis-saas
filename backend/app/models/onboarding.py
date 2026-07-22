from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class OnboardingTemplate(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'onboarding_templates'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    tasks = db.relationship('OnboardingTask', back_populates='template', cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('tenant_id', 'name', name='uq_onboarding_templates_tenant_name'),)

    def to_dict(self):
        return {'id': str(self.id), 'tenant_id': str(self.tenant_id), 'name': self.name, 'description': self.description, 'is_active': self.is_active, 'tasks': [task.to_dict() for task in self.tasks]}


class OnboardingTask(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'onboarding_tasks'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    template_id = db.Column(GUID(), db.ForeignKey('onboarding_templates.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    assignee_role = db.Column(db.String(40), nullable=False, default='EMPLOYEE')
    due_days_after_start = db.Column(db.Integer, nullable=False, default=0)
    required = db.Column(db.Boolean, nullable=False, default=True)

    template = db.relationship('OnboardingTemplate', back_populates='tasks')
    assignments = db.relationship('EmployeeOnboardingTask', back_populates='task', cascade='all, delete-orphan')

    __table_args__ = (db.CheckConstraint("assignee_role IN ('EMPLOYEE','MANAGER','CLIENT_ADMIN','HR_CONSULTANT')", name='ck_onboarding_tasks_assignee_role'),)

    def to_dict(self):
        return {'id': str(self.id), 'template_id': str(self.template_id), 'title': self.title, 'description': self.description, 'assignee_role': self.assignee_role, 'due_days_after_start': self.due_days_after_start, 'required': self.required}


class EmployeeOnboardingTask(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'employee_onboarding_tasks'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    task_id = db.Column(GUID(), db.ForeignKey('onboarding_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    assigned_to_user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    status = db.Column(db.String(40), nullable=False, default='pending', index=True)
    due_date = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    completion_notes = db.Column(db.Text)

    employee = db.relationship('Employee', back_populates='onboarding_assignments')
    task = db.relationship('OnboardingTask', back_populates='assignments')
    assigned_to = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'employee_id', 'task_id', name='uq_employee_onboarding_task'),
        db.CheckConstraint("status IN ('pending','in_progress','completed','waived','overdue')", name='ck_employee_onboarding_tasks_status'),
    )

    def to_dict(self):
        return {'id': str(self.id), 'employee_id': str(self.employee_id), 'task_id': str(self.task_id), 'assigned_to_user_id': str(self.assigned_to_user_id) if self.assigned_to_user_id else None, 'status': self.status, 'due_date': self.due_date.isoformat() if self.due_date else None, 'completed_at': self.completed_at.isoformat() if self.completed_at else None, 'completion_notes': self.completion_notes}
