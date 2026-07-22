from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


class EmergencyContact(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'emergency_contacts'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    employee_id = db.Column(GUID(), db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    relationship = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    employee = db.relationship('Employee', back_populates='emergency_contacts')

    def to_dict(self):
        return {'id': str(self.id), 'employee_id': str(self.employee_id), 'name': self.name, 'relationship': self.relationship, 'phone': self.phone, 'email': self.email, 'is_primary': self.is_primary}
