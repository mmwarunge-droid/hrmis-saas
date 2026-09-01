from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class OnboardingResource(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'onboarding_resources'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    uploaded_by_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    resource_type = db.Column(db.String(20), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer)

    uploaded_by = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint(
            "resource_type IN ('document','video')",
            name='ck_onboarding_resources_type',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'uploaded_by_id': (
                str(self.uploaded_by_id) if self.uploaded_by_id else None
            ),
            'resource_type': self.resource_type,
            'original_filename': self.original_filename,
            'mime_type': self.mime_type,
            'size_bytes': self.size_bytes,
        }


class OnboardingTemplate(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'onboarding_templates'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    tasks = db.relationship(
        'OnboardingTask',
        back_populates='template',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'name',
            name='uq_onboarding_templates_tenant_name',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'tasks': [task.to_dict() for task in self.tasks],
        }


class OnboardingTask(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'onboarding_tasks'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    template_id = db.Column(
        GUID(),
        db.ForeignKey('onboarding_templates.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    resource_id = db.Column(
        GUID(),
        db.ForeignKey('onboarding_resources.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    task_type = db.Column(db.String(20), nullable=False, default='action')
    assignee_role = db.Column(
        db.String(40),
        nullable=False,
        default='EMPLOYEE',
    )
    due_days_after_start = db.Column(db.Integer, nullable=False, default=0)
    required = db.Column(db.Boolean, nullable=False, default=True)
    requires_acknowledgement = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    template = db.relationship('OnboardingTemplate', back_populates='tasks')
    resource = db.relationship('OnboardingResource')
    assignments = db.relationship(
        'EmployeeOnboardingTask',
        back_populates='task',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.CheckConstraint(
            "assignee_role IN ('EMPLOYEE','MANAGER','CLIENT_ADMIN','HR_CONSULTANT')",
            name='ck_onboarding_tasks_assignee_role',
        ),
        db.CheckConstraint(
            "task_type IN ('action','document','video')",
            name='ck_onboarding_tasks_type',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'template_id': str(self.template_id),
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'resource_id': str(self.resource_id) if self.resource_id else None,
            'resource': self.resource.to_dict() if self.resource else None,
            'assignee_role': self.assignee_role,
            'due_days_after_start': self.due_days_after_start,
            'required': self.required,
            'requires_acknowledgement': self.requires_acknowledgement,
        }


class EmployeeOnboardingTask(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'employee_onboarding_tasks'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    task_id = db.Column(
        GUID(),
        db.ForeignKey('onboarding_tasks.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    assigned_to_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status = db.Column(
        db.String(40),
        nullable=False,
        default='pending',
        index=True,
    )
    due_date = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    resource_viewed_at = db.Column(db.DateTime)
    acknowledged_at = db.Column(db.DateTime)
    completion_notes = db.Column(db.Text)

    employee = db.relationship(
        'Employee',
        back_populates='onboarding_assignments',
    )
    task = db.relationship('OnboardingTask', back_populates='assignments')
    assigned_to = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'employee_id',
            'task_id',
            name='uq_employee_onboarding_task',
        ),
        db.CheckConstraint(
            "status IN ('pending','in_progress','completed','waived','overdue')",
            name='ck_employee_onboarding_tasks_status',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'employee_id': str(self.employee_id),
            'task_id': str(self.task_id),
            'assigned_to_user_id': (
                str(self.assigned_to_user_id)
                if self.assigned_to_user_id
                else None
            ),
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            'resource_viewed_at': (
                self.resource_viewed_at.isoformat()
                if self.resource_viewed_at
                else None
            ),
            'acknowledged_at': (
                self.acknowledged_at.isoformat()
                if self.acknowledged_at
                else None
            ),
            'completion_notes': self.completion_notes,
        }
