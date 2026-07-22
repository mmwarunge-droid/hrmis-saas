from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class JobHistory(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'job_histories'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    job_title = db.Column(db.String(160), nullable=False)
    department_id = db.Column(GUID(), db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    manager_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    reason = db.Column(db.String(255))
    compensation_band = db.Column(db.String(80))

    employee = db.relationship('Employee', back_populates='job_histories', foreign_keys=[employee_id])
    department = db.relationship('Department')
    manager = db.relationship('Employee', foreign_keys=[manager_id])

    __table_args__ = (db.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_job_history_date_range'),)

    def to_dict(self):
        return {'id': str(self.id), 'employee_id': str(self.employee_id), 'job_title': self.job_title, 'start_date': self.start_date.isoformat() if self.start_date else None, 'end_date': self.end_date.isoformat() if self.end_date else None}
