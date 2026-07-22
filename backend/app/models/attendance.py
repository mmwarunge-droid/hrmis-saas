from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class AttendanceRecord(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'attendance_records'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    check_in_at = db.Column(db.DateTime)
    check_out_at = db.Column(db.DateTime)
    source = db.Column(db.String(60), nullable=False, default='self_service')
    notes = db.Column(db.Text)

    employee = db.relationship('Employee', back_populates='attendance_records')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'employee_id', 'work_date', name='uq_attendance_tenant_employee_day'),
        db.CheckConstraint('check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at', name='ck_attendance_time_order'),
    )

    def to_dict(self):
        return {'id': str(self.id), 'employee_id': str(self.employee_id), 'work_date': self.work_date.isoformat() if self.work_date else None, 'check_in_at': self.check_in_at.isoformat() if self.check_in_at else None, 'check_out_at': self.check_out_at.isoformat() if self.check_out_at else None, 'source': self.source, 'notes': self.notes}
