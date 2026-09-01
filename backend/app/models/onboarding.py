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
    duration_seconds = db.Column(db.Float)

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
            'duration_seconds': self.duration_seconds,
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
    max_attempts = db.Column(db.Integer, nullable=False, default=1)
    pass_mark_percent = db.Column(db.Float)

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
        db.CheckConstraint(
            'max_attempts >= 1 AND max_attempts <= 20',
            name='ck_onboarding_tasks_max_attempts',
        ),
        db.CheckConstraint(
            'pass_mark_percent IS NULL OR '
            '(pass_mark_percent >= 0 AND pass_mark_percent <= 100)',
            name='ck_onboarding_tasks_pass_mark',
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
            'max_attempts': self.max_attempts,
            'pass_mark_percent': self.pass_mark_percent,
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
    video_verified_seconds = db.Column(
        db.Float,
        nullable=False,
        default=0.0,
    )
    video_last_position_seconds = db.Column(
        db.Float,
        nullable=False,
        default=0.0,
    )
    video_last_heartbeat_at = db.Column(db.DateTime)
    video_started_at = db.Column(db.DateTime)
    video_completed_at = db.Column(db.DateTime)
    completion_notes = db.Column(db.Text)
    current_attempt_number = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )
    additional_attempts_granted = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    employee = db.relationship(
        'Employee',
        back_populates='onboarding_assignments',
    )
    task = db.relationship('OnboardingTask', back_populates='assignments')
    assigned_to = db.relationship('User')
    attempts = db.relationship(
        'OnboardingTrainingAttempt',
        back_populates='assignment',
        cascade='all, delete-orphan',
        order_by='OnboardingTrainingAttempt.attempt_number',
    )

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
        db.CheckConstraint(
            'current_attempt_number >= 1',
            name='ck_employee_onboarding_current_attempt',
        ),
        db.CheckConstraint(
            'additional_attempts_granted >= 0',
            name='ck_employee_onboarding_extra_attempts',
        ),
    )

    @property
    def attempt_limit(self):
        return int(self.task.max_attempts or 1) + int(
            self.additional_attempts_granted or 0
        )

    @property
    def attempts_remaining(self):
        return max(self.attempt_limit - self.current_attempt_number, 0)

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
            'video_verified_seconds': float(
                self.video_verified_seconds or 0.0
            ),
            'video_last_position_seconds': float(
                self.video_last_position_seconds or 0.0
            ),
            'video_started_at': (
                self.video_started_at.isoformat()
                if self.video_started_at
                else None
            ),
            'video_completed_at': (
                self.video_completed_at.isoformat()
                if self.video_completed_at
                else None
            ),
            'completion_notes': self.completion_notes,
            'current_attempt_number': self.current_attempt_number,
            'max_attempts': self.task.max_attempts,
            'additional_attempts_granted': (
                self.additional_attempts_granted
            ),
            'attempt_limit': self.attempt_limit,
            'attempts_remaining': self.attempts_remaining,
            'pass_mark_percent': self.task.pass_mark_percent,
        }


class OnboardingTrainingAttempt(
    db.Model,
    TenantMixin,
    TimestampMixin,
    ReprMixin,
):
    __tablename__ = 'onboarding_training_attempts'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    assignment_id = db.Column(
        GUID(),
        db.ForeignKey('employee_onboarding_tasks.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    attempt_number = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default='pending',
        index=True,
    )
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    score_percent = db.Column(db.Float)
    passed = db.Column(db.Boolean)
    time_spent_seconds = db.Column(db.Float, nullable=False, default=0.0)
    authorized_by_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    authorization_reason = db.Column(db.Text)

    assignment = db.relationship(
        'EmployeeOnboardingTask',
        back_populates='attempts',
    )
    authorized_by = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'assignment_id',
            'attempt_number',
            name='uq_onboarding_training_attempt_number',
        ),
        db.CheckConstraint(
            "status IN ('pending','in_progress','completed','failed',"
            "'superseded','waived')",
            name='ck_onboarding_training_attempt_status',
        ),
        db.CheckConstraint(
            'attempt_number >= 1',
            name='ck_onboarding_training_attempt_number',
        ),
        db.CheckConstraint(
            'score_percent IS NULL OR '
            '(score_percent >= 0 AND score_percent <= 100)',
            name='ck_onboarding_training_attempt_score',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'assignment_id': str(self.assignment_id),
            'attempt_number': self.attempt_number,
            'status': self.status,
            'started_at': (
                self.started_at.isoformat() if self.started_at else None
            ),
            'completed_at': (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            'score_percent': self.score_percent,
            'passed': self.passed,
            'time_spent_seconds': float(self.time_spent_seconds or 0.0),
            'authorized_by_user_id': (
                str(self.authorized_by_user_id)
                if self.authorized_by_user_id
                else None
            ),
            'authorized_by_name': (
                self.authorized_by.full_name
                if self.authorized_by
                else None
            ),
            'authorization_reason': self.authorization_reason,
        }
