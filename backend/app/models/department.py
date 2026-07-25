from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TenantMixin, TimestampMixin, uuid_pk


class Department(db.Model, TenantMixin, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'departments'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(140), nullable=False)
    code = db.Column(db.String(40))
    parent_department_id = db.Column(
        GUID(),
        db.ForeignKey('departments.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    head_employee_id = db.Column(
        GUID(),
        db.ForeignKey('employees.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    tenant = db.relationship('Tenant', back_populates='departments')
    parent = db.relationship('Department', remote_side=[id], foreign_keys=[parent_department_id])
    head = db.relationship('Employee', foreign_keys=[head_employee_id], post_update=True)
    employees = db.relationship(
        'Employee',
        back_populates='department',
        foreign_keys='Employee.department_id',
    )

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_departments_tenant_name'),
        db.UniqueConstraint('tenant_id', 'code', name='uq_departments_tenant_code'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'name': self.name,
            'code': self.code,
            'parent_department_id': str(self.parent_department_id) if self.parent_department_id else None,
            'head_employee_id': str(self.head_employee_id) if self.head_employee_id else None,
            'head_name': self.head.full_name if self.head else None,
            'archived': self.deleted_at is not None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }
