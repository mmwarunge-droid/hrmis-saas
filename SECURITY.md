# Security

## Authentication

The backend uses JWT access and refresh tokens. Access tokens include tenant id, roles, and permissions as claims. Passwords are hashed using Flask-Bcrypt. No raw passwords or secrets are hardcoded.

## Authorization and RBAC

RBAC is enforced with backend decorators:

- `@permission_required(...)`
- `@role_required(...)`

The frontend hides unavailable navigation items, but the backend remains the source of authority.

## Tenant isolation

Tenant-specific models carry `tenant_id`. Query access is centralized through `tenant_query(model)`, which restricts non-super-admin users to their tenant. Foreign-key values such as department, manager, employee, leave type, and document employee links are validated against the tenant.

## Document security

Files are sanitized with `secure_filename`, stored under tenant-specific folders, type-checked, size-limited, and checked for path traversal during download. Document metadata includes expiry date, signature status, access level, status, version, checksum, and uploader.

## Secrets management

Use environment variables for `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, CORS origins, upload folder, and token expiry. Render should generate secrets and inject PostgreSQL connection strings.

## Audit logging

Sensitive actions create audit entries: tenant creation/update, user creation/role changes, employee create/update/delete, document upload/update, leave decisions, attendance check-in/out, and onboarding workflow activity.

## Production recommendations

- Add Redis-backed JWT denylist for logout and compromised-token revocation.
- Use object storage with signed URLs instead of persistent local disk for larger deployments.
- Enable PostgreSQL Row Level Security.
- Add SAST/dependency scanning in CI.
- Add rate limits per endpoint class and IP/user.
- Configure backup, restore, and data retention policies per jurisdiction.
