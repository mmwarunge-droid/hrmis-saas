from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TenantMixin, TimestampMixin, uuid_pk


class Employee(db.Model, TenantMixin, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'employees'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    employee_number = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    preferred_name = db.Column(db.String(120))
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(60))
    date_of_birth = db.Column(db.Date)
    national_identifier_last4 = db.Column(db.String(12))
    hire_date = db.Column(db.Date, nullable=False)
    termination_date = db.Column(db.Date)
    employment_status = db.Column(db.String(40), nullable=False, default='active')
    employment_type = db.Column(db.String(60), nullable=False, default='full_time')
    job_title = db.Column(db.String(160))
    department_id = db.Column(GUID(), db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    manager_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True)
    work_location = db.Column(db.String(160))
    address = db.Column(db.Text)
    external_hris_id = db.Column(db.String(120), index=True)

    user = db.relationship('User', back_populates='employee_profile', foreign_keys=[user_id])
    department = db.relationship('Department', back_populates='employees')
    manager = db.relationship('Employee', remote_side=[id], foreign_keys=[manager_id])
    emergency_contacts = db.relationship('EmergencyContact', back_populates='employee', cascade='all, delete-orphan')
    job_histories = db.relationship('JobHistory', back_populates='employee', cascade='all, delete-orphan', foreign_keys='JobHistory.employee_id')
    documents = db.relationship('Document', back_populates='employee')
    leave_balances = db.relationship('LeaveBalance', back_populates='employee', cascade='all, delete-orphan')
    leave_requests = db.relationship('LeaveRequest', back_populates='employee', cascade='all, delete-orphan')
    attendance_records = db.relationship('AttendanceRecord', back_populates='employee', cascade='all, delete-orphan')
    onboarding_assignments = db.relationship('EmployeeOnboardingTask', back_populates='employee', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'employee_number', name='uq_employees_tenant_employee_number'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_employees_tenant_email'),
        db.CheckConstraint("employment_status IN ('active','probation','suspended','terminated')", name='ck_employees_status'),
        db.CheckConstraint("employment_type IN ('full_time','part_time','contractor','intern','temporary')", name='ck_employees_type'),
    )

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def to_dict(self):
        return {
            'id': str(self.id), 'tenant_id': str(self.tenant_id), 'user_id': str(self.user_id) if self.user_id else None,
            'employee_number': self.employee_number, 'first_name': self.first_name, 'last_name': self.last_name,
            'preferred_name': self.preferred_name, 'full_name': self.full_name, 'email': self.email, 'phone': self.phone,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'termination_date': self.termination_date.isoformat() if self.termination_date else None,
            'employment_status': self.employment_status, 'employment_type': self.employment_type,
            'job_title': self.job_title, 'department_id': str(self.department_id) if self.department_id else None,
            'manager_id': str(self.manager_id) if self.manager_id else None, 'work_location': self.work_location,
            'external_hris_id': self.external_hris_id,
        }
