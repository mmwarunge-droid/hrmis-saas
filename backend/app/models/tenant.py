from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TimestampMixin, uuid_pk


class Tenant(db.Model, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'tenants'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(160), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    legal_name = db.Column(db.String(220))
    country = db.Column(db.String(80))
    industry = db.Column(db.String(120))
    status = db.Column(db.String(30), nullable=False, default='active')
    billing_plan = db.Column(db.String(60), nullable=False, default='mvp')
    compliance_region = db.Column(db.String(80))
    organization_owner_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    leave_alternate_approver_user_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    leave_setup_completed_at = db.Column(db.DateTime, nullable=True)

    users = db.relationship(
        'User',
        back_populates='tenant',
        passive_deletes=True,
        foreign_keys='User.tenant_id',
    )
    departments = db.relationship(
        'Department',
        back_populates='tenant',
        passive_deletes=True,
    )
    organization_owner = db.relationship(
        'User',
        foreign_keys=[organization_owner_user_id],
        post_update=True,
    )
    leave_alternate_approver = db.relationship(
        'User',
        foreign_keys=[leave_alternate_approver_user_id],
        post_update=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active','suspended','archived')",
            name='ck_tenants_status',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'legal_name': self.legal_name,
            'country': self.country,
            'industry': self.industry,
            'status': self.status,
            'billing_plan': self.billing_plan,
            'compliance_region': self.compliance_region,
            'organization_owner_user_id': (
                str(self.organization_owner_user_id)
                if self.organization_owner_user_id
                else None
            ),
            'leave_alternate_approver_user_id': (
                str(self.leave_alternate_approver_user_id)
                if self.leave_alternate_approver_user_id
                else None
            ),
            'leave_setup_completed_at': (
                self.leave_setup_completed_at.isoformat()
                if self.leave_setup_completed_at
                else None
            ),
        }
