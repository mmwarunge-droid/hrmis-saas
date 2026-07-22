from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class LeaveType(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_types'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(100), nullable=False)
    annual_entitlement_days = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    accrual_method = db.Column(db.String(40), nullable=False, default='annual')
    requires_approval = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    carryover_allowed = db.Column(db.Boolean, nullable=False, default=False)
    max_carryover_days = db.Column(db.Numeric(6, 2), nullable=False, default=0)

    balances = db.relationship('LeaveBalance', back_populates='leave_type', cascade='all, delete-orphan')
    requests = db.relationship('LeaveRequest', back_populates='leave_type')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_leave_types_tenant_name'),
        db.CheckConstraint("accrual_method IN ('annual','monthly','manual','none')", name='ck_leave_types_accrual_method'),
    )

    def to_dict(self):
        return {'id': str(self.id), 'tenant_id': str(self.tenant_id), 'name': self.name, 'annual_entitlement_days': float(self.annual_entitlement_days or 0), 'accrual_method': self.accrual_method, 'requires_approval': self.requires_approval, 'is_active': self.is_active}


class LeaveBalance(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_balances'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    leave_type_id = db.Column(GUID(), db.ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False, index=True)
    balance_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    accrued_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    used_days = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    year = db.Column(db.Integer, nullable=False, index=True)

    employee = db.relationship('Employee', back_populates='leave_balances')
    leave_type = db.relationship('LeaveType', back_populates='balances')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'employee_id', 'leave_type_id', 'year', name='uq_leave_balances_tenant_employee_type_year'),
    )

    def to_dict(self):
        return {'id': str(self.id), 'employee_id': str(self.employee_id), 'leave_type_id': str(self.leave_type_id), 'balance_days': float(self.balance_days or 0), 'accrued_days': float(self.accrued_days or 0), 'used_days': float(self.used_days or 0), 'year': self.year}


class LeaveRequest(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_requests'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    leave_type_id = db.Column(GUID(), db.ForeignKey('leave_types.id', ondelete='RESTRICT'), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Numeric(8, 2), nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(40), nullable=False, default='pending', index=True)
    approver_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    decision_notes = db.Column(db.Text)
    decided_at = db.Column(db.DateTime)

    employee = db.relationship('Employee', back_populates='leave_requests')
    leave_type = db.relationship('LeaveType', back_populates='requests')
    approver = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint("status IN ('pending','approved','rejected','cancelled')", name='ck_leave_requests_status'),
        db.CheckConstraint('end_date >= start_date', name='ck_leave_requests_date_range'),
        db.CheckConstraint('total_days > 0', name='ck_leave_requests_total_days_positive'),
    )

    def to_dict(self):
        return {
            'id': str(self.id), 'employee_id': str(self.employee_id), 'leave_type_id': str(self.leave_type_id),
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_days': float(self.total_days or 0), 'reason': self.reason, 'status': self.status,
            'approver_id': str(self.approver_id) if self.approver_id else None,
            'decision_notes': self.decision_notes, 'decided_at': self.decided_at.isoformat() if self.decided_at else None,
        }
