# Production Readiness Program

## Step 1 — Application and build foundation: complete

- Restored the Flask application factory.
- Initialized SQLAlchemy, migrations, JWT, CORS, rate limiting, bcrypt, and error handling.
- Added JWT user lookup and consistent authentication errors.
- Preserved Blueprint resource prefixes under `/api`.
- Added `/health` and `/ready` endpoints.
- Removed public first-user `SUPER_ADMIN` bootstrap.
- Added a one-time, fail-closed `bootstrap-admin` CLI command.
- Prevented tenant administrators from assigning platform-wide roles.
- Corrected employee tenant handling and role permissions exposed by the test suite.
- Pinned frontend dependencies and committed `package-lock.json`.
- Corrected Vitest and ESLint configuration.
- Added a required production API URL guard.
- Added hardened Vercel routing, caching, and baseline response headers.
- Updated CI to use `npm ci`, Node 22, and PostgreSQL migration validation.

Validation status:

- Backend Ruff: passing.
- Backend tests: 13 passing.
- Frontend ESLint: passing with no warnings.
- Frontend tests: 4 passing.
- Frontend production build: passing.
- Frontend production dependency audit: zero known vulnerabilities.

## Step 2 — Authentication and session security

- Completed in Step 2A: replaced browser `localStorage` tokens with Secure, HttpOnly cookies.
- Completed in Step 2A: added double-submit CSRF defenses for mutating requests.
- Completed in Step 2B: refresh-token rotation, reuse detection, persistent sessions, and Redis-backed JTI/session revocation.
- Completed in Step 2B: session listing, individual forced logout, and logout-all controls.
- Completed in Step 2C: account lockout with configurable failure windows and recovery.
- Completed in Step 2C: privacy-safe authentication audit events and suspicious-login flags.
- Add password reset and email verification.
- Add MFA for privileged roles.

## Step 3 — Document security and storage

- Replace local filesystem uploads with private object storage.
- Add signed, short-lived downloads and authorization checks.
- Add malware scanning, file signature validation, encryption controls, retention, and deletion workflows.

## Step 4 — Database and tenancy assurance

- Run application tests against PostgreSQL.
- Add migration upgrade/downgrade tests.
- Review every unique constraint for tenant scope.
- Add database-level tenant invariants and concurrency tests.
- Establish backup, point-in-time recovery, and restore drills.

## Step 5 — Observability and operational resilience

- Add structured JSON logs and correlation IDs.
- Add privacy-safe error monitoring, metrics, tracing, and alerting.
- Add Redis-backed distributed rate limits.
- Add deployment smoke tests, rollback procedures, and incident runbooks.

## Step 6 — HRMIS security and compliance controls

- Data classification, access review, and least-privilege role redesign.
- Audit-log integrity and retention.
- Privacy rights, retention schedules, data export, and deletion workflows.
- Security headers tightened to exact production domains.
- Threat model, penetration test, dependency scanning, and secrets scanning.
