from decimal import Decimal

from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


LEDGER_EVENT_TYPES = (
    'BASELINE_IMPORT',
    'OPENING_BALANCE',
    'ACCRUAL',
    'CARRYOVER',
    'MANUAL_ADJUSTMENT',
    'REQUEST_RESERVED',
    'REQUEST_APPROVED',
    'REQUEST_CANCELLED',
    'REQUEST_RESTORED',
    'EXPIRY',
)


class LeaveType(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_types'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    code = db.Column(db.String(80), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    annual_entitlement_days = db.Column(
        db.Numeric(6, 2),
        nullable=False,
        default=0,
    )
    accrual_method = db.Column(
        db.String(40),
        nullable=False,
        default='annual',
    )
    entitlement_mode = db.Column(
        db.String(40),
        nullable=False,
        default='granted_upfront',
    )
    pay_percentage = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=100,
    )
    eligibility_after_months = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )
    requires_approval = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    carryover_allowed = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    max_carryover_days = db.Column(
        db.Numeric(6, 2),
        nullable=False,
        default=0,
    )
    carryover_expiry_months = db.Column(
        db.Integer,
        nullable=True,
    )
    allow_negative_balance = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    minimum_notice_days = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )
    documentation_after_days = db.Column(
        db.Integer,
        nullable=True,
    )

    balances = db.relationship(
        'LeaveBalance',
        back_populates='leave_type',
        cascade='all, delete-orphan',
    )
    requests = db.relationship(
        'LeaveRequest',
        back_populates='leave_type',
    )
    ledger_entries = db.relationship(
        'LeaveLedgerEntry',
        back_populates='leave_type',
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'name',
            name='uq_leave_types_tenant_name',
        ),
        db.UniqueConstraint(
            'tenant_id',
            'code',
            name='uq_leave_types_tenant_code',
        ),
        db.CheckConstraint(
            "accrual_method IN ('annual','monthly','manual','none')",
            name='ck_leave_types_accrual_method',
        ),
        db.CheckConstraint(
            "entitlement_mode IN ("
            "'accrued','granted_upfront','event_based','unlimited','manual'"
            ")",
            name='ck_leave_types_entitlement_mode',
        ),
        db.CheckConstraint(
            'pay_percentage >= 0 AND pay_percentage <= 100',
            name='ck_leave_types_pay_percentage',
        ),
        db.CheckConstraint(
            'eligibility_after_months >= 0',
            name='ck_leave_types_eligibility_months',
        ),
        db.CheckConstraint(
            'minimum_notice_days >= 0',
            name='ck_leave_types_minimum_notice_days',
        ),
        db.CheckConstraint(
            'documentation_after_days IS NULL '
            'OR documentation_after_days >= 0',
            name='ck_leave_types_documentation_after_days',
        ),
        db.CheckConstraint(
            'carryover_expiry_months IS NULL '
            'OR carryover_expiry_months >= 0',
            name='ck_leave_types_carryover_expiry_months',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'code': self.code,
            'name': self.name,
            'annual_entitlement_days': float(
                self.annual_entitlement_days or 0,
            ),
            'accrual_method': self.accrual_method,
            'entitlement_mode': self.entitlement_mode,
            'pay_percentage': float(self.pay_percentage or 0),
            'eligibility_after_months': self.eligibility_after_months,
            'requires_approval': self.requires_approval,
            'is_active': self.is_active,
            'carryover_allowed': self.carryover_allowed,
            'max_carryover_days': float(
                self.max_carryover_days or 0,
            ),
            'carryover_expiry_months': self.carryover_expiry_months,
            'allow_negative_balance': self.allow_negative_balance,
            'minimum_notice_days': self.minimum_notice_days,
            'documentation_after_days': self.documentation_after_days,
            'is_unlimited': self.entitlement_mode == 'unlimited',
        }


class LeaveBalance(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_balances'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    leave_type_id = db.Column(
        GUID(),
        db.ForeignKey('leave_types.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    opening_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    balance_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    accrued_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    carried_over_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    adjusted_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    used_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    reserved_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    expired_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    carryover_remaining_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    carryover_expires_at = db.Column(db.Date, nullable=True, index=True)
    accrual_through_date = db.Column(db.Date, nullable=True, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)

    employee = db.relationship(
        'Employee',
        back_populates='leave_balances',
    )
    leave_type = db.relationship(
        'LeaveType',
        back_populates='balances',
    )
    ledger_entries = db.relationship(
        'LeaveLedgerEntry',
        back_populates='leave_balance',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'employee_id',
            'leave_type_id',
            'year',
            name='uq_leave_balances_tenant_employee_type_year',
        ),
        db.CheckConstraint(
            'reserved_days >= 0',
            name='ck_leave_balances_reserved_nonnegative',
        ),
        db.CheckConstraint(
            'carryover_remaining_days >= 0',
            name='ck_leave_balances_carryover_remaining_nonnegative',
        ),
    )

    @property
    def allocated_days(self):
        return (
            Decimal(self.opening_days or 0)
            + Decimal(self.accrued_days or 0)
            + Decimal(self.carried_over_days or 0)
            + Decimal(self.adjusted_days or 0)
            - Decimal(self.expired_days or 0)
        )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'employee_id': str(self.employee_id),
            'leave_type_id': str(self.leave_type_id),
            'opening_days': float(self.opening_days or 0),
            'balance_days': float(self.balance_days or 0),
            'available_days': float(self.balance_days or 0),
            'allocated_days': float(self.allocated_days),
            'accrued_days': float(self.accrued_days or 0),
            'carried_over_days': float(self.carried_over_days or 0),
            'adjusted_days': float(self.adjusted_days or 0),
            'used_days': float(self.used_days or 0),
            'reserved_days': float(self.reserved_days or 0),
            'expired_days': float(self.expired_days or 0),
            'carryover_remaining_days': float(
                self.carryover_remaining_days or 0,
            ),
            'carryover_expires_at': (
                self.carryover_expires_at.isoformat()
                if self.carryover_expires_at
                else None
            ),
            'accrual_through_date': (
                self.accrual_through_date.isoformat()
                if self.accrual_through_date
                else None
            ),
            'year': self.year,
        }


class LeaveRequest(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_requests'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    leave_type_id = db.Column(
        GUID(),
        db.ForeignKey('leave_types.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Numeric(8, 2), nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(
        db.String(40),
        nullable=False,
        default='pending',
        index=True,
    )
    requested_by_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    required_approver_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    approver_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    approval_route = db.Column(db.String(80), nullable=True)
    balance_reserved_at = db.Column(db.DateTime, nullable=True, index=True)
    reserved_carryover_days = db.Column(
        db.Numeric(8, 2),
        nullable=False,
        default=0,
    )
    decision_notes = db.Column(db.Text)
    decided_at = db.Column(db.DateTime)

    employee = db.relationship(
        'Employee',
        back_populates='leave_requests',
    )
    leave_type = db.relationship(
        'LeaveType',
        back_populates='requests',
    )
    requested_by = db.relationship(
        'User',
        foreign_keys=[requested_by_user_id],
    )
    required_approver = db.relationship(
        'User',
        foreign_keys=[required_approver_id],
    )
    approver = db.relationship(
        'User',
        foreign_keys=[approver_id],
    )
    ledger_entries = db.relationship(
        'LeaveLedgerEntry',
        back_populates='leave_request',
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name='ck_leave_requests_status',
        ),
        db.CheckConstraint(
            'end_date >= start_date',
            name='ck_leave_requests_date_range',
        ),
        db.CheckConstraint(
            'total_days > 0',
            name='ck_leave_requests_total_days_positive',
        ),
        db.CheckConstraint(
            'reserved_carryover_days >= 0',
            name='ck_leave_requests_reserved_carryover_nonnegative',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'employee_id': str(self.employee_id),
            'leave_type_id': str(self.leave_type_id),
            'start_date': (
                self.start_date.isoformat()
                if self.start_date
                else None
            ),
            'end_date': (
                self.end_date.isoformat()
                if self.end_date
                else None
            ),
            'total_days': float(self.total_days or 0),
            'reason': self.reason,
            'status': self.status,
            'requested_by_user_id': (
                str(self.requested_by_user_id)
                if self.requested_by_user_id
                else None
            ),
            'required_approver_id': (
                str(self.required_approver_id)
                if self.required_approver_id
                else None
            ),
            'approver_id': (
                str(self.approver_id)
                if self.approver_id
                else None
            ),
            'approval_route': self.approval_route,
            'balance_reserved_at': (
                self.balance_reserved_at.isoformat()
                if self.balance_reserved_at
                else None
            ),
            'reserved_carryover_days': float(
                self.reserved_carryover_days or 0,
            ),
            'decision_notes': self.decision_notes,
            'decided_at': (
                self.decided_at.isoformat()
                if self.decided_at
                else None
            ),
        }


class LeaveLedgerEntry(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'leave_ledger_entries'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    leave_type_id = db.Column(
        GUID(),
        db.ForeignKey('leave_types.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    leave_balance_id = db.Column(
        GUID(),
        db.ForeignKey('leave_balances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    leave_request_id = db.Column(
        GUID(),
        db.ForeignKey('leave_requests.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    actor_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    event_type = db.Column(db.String(40), nullable=False, index=True)
    amount_days = db.Column(db.Numeric(10, 2), nullable=False)
    balance_after_days = db.Column(db.Numeric(10, 2), nullable=False)
    effective_date = db.Column(db.Date, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    idempotency_key = db.Column(db.String(180), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    employee = db.relationship(
        'Employee',
        back_populates='leave_ledger_entries',
    )
    leave_type = db.relationship(
        'LeaveType',
        back_populates='ledger_entries',
    )
    leave_balance = db.relationship(
        'LeaveBalance',
        back_populates='ledger_entries',
    )
    leave_request = db.relationship(
        'LeaveRequest',
        back_populates='ledger_entries',
    )
    actor = db.relationship('User', foreign_keys=[actor_user_id])

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'idempotency_key',
            name='uq_leave_ledger_tenant_idempotency',
        ),
        db.CheckConstraint(
            "event_type IN ("
            + ','.join(f"'{value}'" for value in LEDGER_EVENT_TYPES)
            + ")",
            name='ck_leave_ledger_event_type',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'employee_id': str(self.employee_id),
            'leave_type_id': str(self.leave_type_id),
            'leave_balance_id': str(self.leave_balance_id),
            'leave_request_id': (
                str(self.leave_request_id)
                if self.leave_request_id
                else None
            ),
            'actor_user_id': (
                str(self.actor_user_id)
                if self.actor_user_id
                else None
            ),
            'event_type': self.event_type,
            'amount_days': float(self.amount_days or 0),
            'balance_after_days': float(
                self.balance_after_days or 0,
            ),
            'effective_date': self.effective_date.isoformat(),
            'year': self.year,
            'idempotency_key': self.idempotency_key,
            'reason': self.reason,
            'metadata_json': self.metadata_json or {},
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }
