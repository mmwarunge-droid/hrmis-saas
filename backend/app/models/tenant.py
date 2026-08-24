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
    mfa_policy_mode = db.Column(
        db.String(40),
        nullable=False,
        default='optional',
    )
    mfa_enrollment_grace_days = db.Column(
        db.Integer,
        nullable=False,
        default=14,
    )
    mfa_enforcement_date = db.Column(db.Date, nullable=True)
    mfa_policy_updated_at = db.Column(db.DateTime, nullable=True)
    mfa_policy_updated_by_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    duplicate_job_title_warning_titles = db.Column(
        db.JSON,
        nullable=False,
        default=list,
    )

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
    mfa_policy_updated_by = db.relationship(
        'User',
        foreign_keys=[mfa_policy_updated_by_id],
        post_update=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active','suspended','archived')",
            name='ck_tenants_status',
        ),
        db.CheckConstraint(
            "mfa_policy_mode IN ("
            "'optional','privileged',"
            "'managers_and_privileged','all_users'"
            ")",
            name='ck_tenants_mfa_policy_mode',
        ),
        db.CheckConstraint(
            'mfa_enrollment_grace_days >= 0 '
            'AND mfa_enrollment_grace_days <= 365',
            name='ck_tenants_mfa_grace_days',
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
            'mfa_policy_mode': self.mfa_policy_mode,
            'mfa_enrollment_grace_days': (
                self.mfa_enrollment_grace_days
            ),
            'mfa_enforcement_date': (
                self.mfa_enforcement_date.isoformat()
                if self.mfa_enforcement_date
                else None
            ),
            'mfa_policy_updated_at': (
                self.mfa_policy_updated_at.isoformat()
                if self.mfa_policy_updated_at
                else None
            ),
            'mfa_policy_updated_by_id': (
                str(self.mfa_policy_updated_by_id)
                if self.mfa_policy_updated_by_id
                else None
            ),
            'duplicate_job_title_warning_titles': list(
                self.duplicate_job_title_warning_titles or []
            ),
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            'updated_at': (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }
