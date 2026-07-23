# Security

## Authentication

The backend uses short-lived JWT access tokens and rotating refresh tokens in Secure, HttpOnly cookies with double-submit CSRF protection. Access tokens include tenant id, roles, permissions, and a persistent session id. Redis and the `auth_sessions` table enforce JTI/session revocation and refresh-token reuse detection. Passwords are hashed using Flask-Bcrypt. Configurable failure windows and temporary lockouts slow password guessing while login responses remain account-enumeration resistant. Password reset and email verification use random, single-use tokens; only SHA-256 token hashes are stored, and password changes revoke every active session. No raw passwords or secrets are hardcoded.

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

Use environment variables for `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, CORS origins, upload folder, token expiry, recovery URLs, and SMTP credentials. Render should generate secrets and inject PostgreSQL connection strings.

## Audit logging

Sensitive actions create audit entries: authentication success/failure, account lockout, suspicious login, password reset and email verification, refresh-token replay, logout and forced session revocation, tenant creation/update, user creation/role changes, employee create/update/delete, document upload/update, leave decisions, attendance check-in/out, and onboarding workflow activity. Authentication audit entries reduce IP precision and store keyed user-agent and identifier fingerprints rather than raw values.

## Production recommendations

- Use a private, persistent Redis deployment for session and JTI revocation state.
- Use authenticated TLS SMTP or a transactional mail gateway; production rejects the development console mail transport.
- Keep password-reset and verification links on HTTPS frontend routes and never log their raw tokens in production.
- Use object storage with signed URLs instead of persistent local disk for larger deployments.
- Enable PostgreSQL Row Level Security.
- Add SAST/dependency scanning in CI.
- Add rate limits per endpoint class and IP/user.
- Configure backup, restore, and data retention policies per jurisdiction.
