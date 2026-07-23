from app.extensions import db
from app.models.base import GUID, ReprMixin, SoftDeleteMixin, TimestampMixin, uuid_pk


class Permission(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'permissions'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    code = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))

    role_links = db.relationship('RolePermission', back_populates='permission', cascade='all, delete-orphan')

    def to_dict(self):
        return {'id': str(self.id), 'code': self.code, 'description': self.description}


class Role(db.Model, TimestampMixin, ReprMixin):
    __tablename__ = 'roles'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    name = db.Column(db.String(60), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, nullable=False, default=True)

    permission_links = db.relationship('RolePermission', back_populates='role', cascade='all, delete-orphan')
    user_links = db.relationship('UserRole', back_populates='role', cascade='all, delete-orphan')

    @property
    def permissions(self):
        return [link.permission for link in self.permission_links]

    @property
    def permission_codes(self):
        return sorted(permission.code for permission in self.permissions)

    def to_dict(self):
        return {'id': str(self.id), 'name': self.name, 'permissions': self.permission_codes}


class RolePermission(db.Model, TimestampMixin):
    __tablename__ = 'role_permissions'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    role_id = db.Column(GUID(), db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_id = db.Column(GUID(), db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True)

    role = db.relationship('Role', back_populates='permission_links')
    permission = db.relationship('Permission', back_populates='role_links')

    __table_args__ = (db.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),)


class UserRole(db.Model, TimestampMixin):
    __tablename__ = 'user_roles'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role_id = db.Column(GUID(), db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)
    assigned_by_id = db.Column(GUID(), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    user = db.relationship('User', back_populates='role_links', foreign_keys=[user_id])
    role = db.relationship('Role', back_populates='user_links')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])

    __table_args__ = (db.UniqueConstraint('user_id', 'role_id', name='uq_user_role'),)


class User(db.Model, TimestampMixin, SoftDeleteMixin, ReprMixin):
    __tablename__ = 'users'

    id = db.Column(GUID(), primary_key=True, default=uuid_pk)
    tenant_id = db.Column(GUID(), db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    last_failed_login_at = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True, index=True)
    email_verified_at = db.Column(db.DateTime, nullable=True, index=True)

    tenant = db.relationship('Tenant', back_populates='users')
    role_links = db.relationship('UserRole', back_populates='user', cascade='all, delete-orphan', foreign_keys=[UserRole.user_id])
    employee_profile = db.relationship('Employee', back_populates='user', uselist=False, foreign_keys='Employee.user_id')
    notifications = db.relationship('Notification', back_populates='user', passive_deletes=True)
    auth_sessions = db.relationship('AuthSession', back_populates='user', cascade='all, delete-orphan')
    account_tokens = db.relationship('AccountToken', back_populates='user', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def roles(self):
        return [link.role for link in self.role_links]

    @property
    def role_names(self):
        return sorted(role.name for role in self.roles)

    @property
    def permission_codes(self):
        codes = set()
        for role in self.roles:
            codes.update(role.permission_codes)
        return sorted(codes)

    def has_role(self, role: str) -> bool:
        return role in self.role_names

    def has_any_role(self, roles: set[str]) -> bool:
        return bool(set(self.role_names).intersection(roles))

    def has_permissions(self, permissions: set[str]) -> bool:
        if self.has_role('SUPER_ADMIN'):
            return True
        return permissions.issubset(set(self.permission_codes))

    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id) if self.tenant_id else None,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'email_verified': self.email_verified_at is not None,
            'email_verified_at': self.email_verified_at.isoformat() if self.email_verified_at else None,
            'roles': self.role_names,
            'permissions': self.permission_codes,
        }
