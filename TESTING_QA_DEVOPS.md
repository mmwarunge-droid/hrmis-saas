# Testing, QA, and DevOps

## Testing layers

- **Unit tests:** services, validators, permission helpers.
- **API tests:** auth, RBAC, tenant isolation, employee CRUD, documents, leave, onboarding.
- **Frontend tests:** login form, protected routes, employee form, error states.
- **E2E recommendation:** Add Playwright flows for login, employee creation, document upload, leave request/approval, and onboarding completion.

## Manual QA checklist

- Bootstrap first super admin user.
- Create tenant and tenant admin.
- Verify client admin cannot access another tenant's employees.
- Create employee, update job title, soft-delete employee.
- Upload document and verify role/access behavior.
- Submit, approve, and reject leave requests.
- Check attendance check-in/out validation.
- Create onboarding template, assign to employee, complete task.
- Confirm dashboard counts and compliance alerts.

## Regression checklist

- Auth tokens expire and protected routes reject missing tokens.
- RBAC blocks unauthorized API calls.
- Tenant payload override is ignored for non-super-admin users.
- Foreign keys are tenant-validated.
- Documents cannot be downloaded across tenants.
- Soft-deleted records do not appear in normal lists.

## Security testing checklist

- Attempt cross-tenant IDOR access.
- Attempt upload of disallowed file extensions.
- Attempt path traversal on document download.
- Attempt role escalation via API payload.
- Confirm production does not expose stack traces.
- Confirm CORS rejects unauthorized origins.

## Deployment smoke test checklist

- `/health` endpoint returns OK.
- Migrations are at head.
- Login succeeds.
- Frontend can call API.
- CORS is configured correctly.
- File upload persists after deployment restart if disk/object storage is configured.

## Rollback plan

- Tag releases.
- Use Alembic downgrade only for reversible schema changes.
- Prefer forward fixes for data migrations.
- Restore database from managed backup if data integrity is compromised.
