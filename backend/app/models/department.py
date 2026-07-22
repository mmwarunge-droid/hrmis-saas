from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TenantMixin, TimestampMixin, uuid_pk


class Department(db.Model, TenantMixin, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'departments'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(140), nullable=False)
    code = db.Column(db.String(40))
    parent_department_id = db.Column(GUID(), db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)

    tenant = db.relationship('Tenant', back_populates='departments')
    parent = db.relationship('Department', remote_side=[id])
    employees = db.relationship('Employee', back_populates='department')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_departments_tenant_name'),
        db.UniqueConstraint('tenant_id', 'code', name='uq_departments_tenant_code'),
    )

    def to_dict(self):
        return {'id': str(self.id), 'tenant_id': str(self.tenant_id), 'name': self.name, 'code': self.code}
