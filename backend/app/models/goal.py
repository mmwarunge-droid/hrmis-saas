from decimal import Decimal

from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class Goal(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'goals'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner_type = db.Column(db.String(30), nullable=False, default='employee', index=True)
    employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    department_id = db.Column(
        GUID(),
        db.ForeignKey('departments.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_by_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(30), nullable=False, default='active', index=True)
    health = db.Column(db.String(30), nullable=False, default='on_track', index=True)
    target_value = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal('100'))
    current_value = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal('0'))
    unit = db.Column(db.String(40), nullable=False, default='%')
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    progress_percent = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal('0'))
    weight = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal('100'))
    last_check_in_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship('Employee', foreign_keys=[employee_id])
    department = db.relationship('Department', foreign_keys=[department_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    check_ins = db.relationship(
        'GoalCheckIn',
        back_populates='goal',
        cascade='all, delete-orphan',
        order_by='GoalCheckIn.created_at.desc()',
    )

    __table_args__ = (
        db.CheckConstraint(
            "owner_type IN ('organization','department','employee')",
            name='ck_goals_owner_type',
        ),
        db.CheckConstraint(
            "status IN ('draft','active','completed','cancelled')",
            name='ck_goals_status',
        ),
        db.CheckConstraint(
            "health IN ('on_track','at_risk','off_track','completed')",
            name='ck_goals_health',
        ),
        db.CheckConstraint(
            'target_value > 0',
            name='ck_goals_target_positive',
        ),
        db.CheckConstraint(
            'progress_percent BETWEEN 0 AND 100',
            name='ck_goals_progress_range',
        ),
        db.CheckConstraint(
            'weight BETWEEN 0 AND 100',
            name='ck_goals_weight_range',
        ),
        db.CheckConstraint(
            "(owner_type = 'organization' AND employee_id IS NULL AND department_id IS NULL) OR "
            "(owner_type = 'department' AND department_id IS NOT NULL AND employee_id IS NULL) OR "
            "(owner_type = 'employee' AND employee_id IS NOT NULL)",
            name='ck_goals_owner_reference',
        ),
    )

    def to_dict(self, include_check_ins=False):
        data = {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'title': self.title,
            'description': self.description,
            'owner_type': self.owner_type,
            'employee_id': str(self.employee_id) if self.employee_id else None,
            'employee_name': self.employee.full_name if self.employee else None,
            'department_id': str(self.department_id) if self.department_id else None,
            'department_name': self.department.name if self.department else None,
            'created_by_user_id': (
                str(self.created_by_user_id)
                if self.created_by_user_id
                else None
            ),
            'created_by_name': self.created_by.full_name if self.created_by else None,
            'status': self.status,
            'health': self.health,
            'target_value': float(self.target_value or 0),
            'current_value': float(self.current_value or 0),
            'unit': self.unit,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'progress_percent': float(self.progress_percent or 0),
            'weight': float(self.weight or 0),
            'last_check_in_at': (
                self.last_check_in_at.isoformat()
                if self.last_check_in_at
                else None
            ),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_check_ins:
            data['check_ins'] = [item.to_dict() for item in self.check_ins]
        return data


class GoalCheckIn(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'goal_check_ins'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    goal_id = db.Column(
        GUID(),
        db.ForeignKey('goals.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    actor_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    current_value = db.Column(db.Numeric(14, 2), nullable=False)
    progress_percent = db.Column(db.Numeric(5, 2), nullable=False)
    health = db.Column(db.String(30), nullable=False)
    note = db.Column(db.Text)

    goal = db.relationship('Goal', back_populates='check_ins')
    actor = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint(
            'progress_percent BETWEEN 0 AND 100',
            name='ck_goal_check_ins_progress_range',
        ),
        db.CheckConstraint(
            "health IN ('on_track','at_risk','off_track','completed')",
            name='ck_goal_check_ins_health',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'goal_id': str(self.goal_id),
            'actor_user_id': str(self.actor_user_id) if self.actor_user_id else None,
            'actor_name': self.actor.full_name if self.actor else 'System',
            'current_value': float(self.current_value or 0),
            'progress_percent': float(self.progress_percent or 0),
            'health': self.health,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
