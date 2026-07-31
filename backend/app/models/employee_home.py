from app.extensions import db
from app.models.base import GUID, ReprMixin, TenantMixin, TimestampMixin, uuid_pk


DEFAULT_HOME_SECTIONS = [
    'birthdays',
    'essentials',
    'people_out_today',
    'events_this_week',
    'new_hires',
    'anniversaries',
    'our_people',
]


class TenantHomepageSettings(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'tenant_homepage_settings'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(
        GUID(),
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )
    banner_url = db.Column(db.String(1000))
    logo_url = db.Column(db.String(1000))
    welcome_message = db.Column(
        db.String(240),
        nullable=False,
        default='Glad you are here.',
    )
    enabled_sections = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: list(DEFAULT_HOME_SECTIONS),
    )
    section_order = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: list(DEFAULT_HOME_SECTIONS),
    )
    new_hire_window_days = db.Column(db.Integer, nullable=False, default=30)
    birthday_visibility_enabled = db.Column(db.Boolean, nullable=False, default=True)
    anniversaries_enabled = db.Column(db.Boolean, nullable=False, default=True)
    people_statistics_enabled = db.Column(db.Boolean, nullable=False, default=True)
    assistant_enabled = db.Column(db.Boolean, nullable=False, default=False)
    assistant_url = db.Column(db.String(1000))

    tenant = db.relationship('Tenant')

    def to_dict(self):
        return {
            'id': str(self.id) if self.id else None,
            'tenant_id': str(self.tenant_id),
            'banner_url': self.banner_url,
            'logo_url': self.logo_url,
            'welcome_message': self.welcome_message,
            'enabled_sections': list(self.enabled_sections or DEFAULT_HOME_SECTIONS),
            'section_order': list(self.section_order or DEFAULT_HOME_SECTIONS),
            'new_hire_window_days': self.new_hire_window_days,
            'birthday_visibility_enabled': self.birthday_visibility_enabled,
            'anniversaries_enabled': self.anniversaries_enabled,
            'people_statistics_enabled': self.people_statistics_enabled,
            'assistant_enabled': self.assistant_enabled,
            'assistant_url': self.assistant_url,
        }


class OrganizationEvent(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'organization_events'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(240))
    meeting_url = db.Column(db.String(1000))
    image_url = db.Column(db.String(1000))
    audience = db.Column(db.String(40), nullable=False, default='all')
    status = db.Column(db.String(30), nullable=False, default='draft', index=True)
    created_by_id = db.Column(
        GUID(),
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    published_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('draft','published','cancelled')",
            name='ck_organization_events_status',
        ),
        db.CheckConstraint(
            "audience IN ('all','employees','managers')",
            name='ck_organization_events_audience',
        ),
        db.CheckConstraint(
            'ends_at IS NULL OR ends_at >= starts_at',
            name='ck_organization_events_range',
        ),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'title': self.title,
            'description': self.description,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'location': self.location,
            'meeting_url': self.meeting_url,
            'image_url': self.image_url,
            'audience': self.audience,
            'status': self.status,
            'created_by_id': str(self.created_by_id) if self.created_by_id else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
        }


class HomepageEssential(db.Model, TenantMixin, TimestampMixin, ReprMixin):
    __tablename__ = 'homepage_essentials'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    document_id = db.Column(
        GUID(),
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    display_title = db.Column(db.String(180))
    display_order = db.Column(db.Integer, nullable=False, default=0)
    importance = db.Column(db.String(30), nullable=False, default='recommended')
    is_published = db.Column(db.Boolean, nullable=False, default=True)

    document = db.relationship('Document')

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'document_id',
            name='uq_homepage_essentials_tenant_document',
        ),
        db.CheckConstraint(
            "importance IN ('required','recommended')",
            name='ck_homepage_essentials_importance',
        ),
    )

    def to_dict(self):
        document = self.document
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'document_id': str(self.document_id),
            'title': self.display_title or getattr(document, 'title', 'Document'),
            'document_type': getattr(document, 'document_type', None),
            'display_order': self.display_order,
            'importance': self.importance,
            'is_published': self.is_published,
            'download_url': f'/api/documents/{self.document_id}/download',
        }
