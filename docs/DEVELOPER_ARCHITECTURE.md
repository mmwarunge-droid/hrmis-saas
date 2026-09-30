# Developer architecture

Start with [CONTRIBUTING](../CONTRIBUTING.md) for commands and [documentation coverage](DOCUMENTATION_COVERAGE.md) for the scope of the September 2026 source review. Operational history lives in the existing deployment and signing runbooks; it is not a substitute for checking the current release SHA.

## Request and persistence boundaries

`frontend/src/App.jsx` composes routes and context providers. Pages call the small `api/*Api.js` wrappers through `apiClient.js`. Axios sends authentication cookies, attaches CSRF headers to mutations, and supplies the selected organization for supported tenant-scoped requests. Its interceptor returns the API response envelope directly; binary responses remain blobs. Forms associate pending requests with a workflow before displaying success or clearing drafts.

`backend/app/__init__.py` creates Flask, registers extensions, request metadata, JWT callbacks, error handlers, health endpoints, CLI commands, and route blueprints. Routes validate schemas and actor access; services coordinate domain changes; models define persistence constraints. Schemas validate shape, not permission. There is no universal service transaction convention: inspect the called function before adding a commit. Some helpers flush for their caller, while session creation, account provisioning, and top-level signing operations commit themselves.

`TenantMixin` adds a column, not an automatic SQL filter. Tenant routes use trusted current-user scope; platform administrators must select a tenant for tenant-scoped operations. Client tenant selection is a usability feature, never authorization. Apply visibility before pagination. Soft deletion similarly requires explicit query filtering. UUID columns and resource route converters reject invalid identifiers before database binding.

## Authentication and employee accounts

JWTs use HTTP-only cookies with CSRF protection. `AuthSession` is authoritative session state; refresh rotation locks the session and stores a hashed refresh JTI. Reuse revokes the session. Redis caches revocation hints, while database checks preserve revocation behavior if the cache is unavailable. Frontend route guards and permission-filtered navigation do not replace backend checks.

Password login checks account, tenant, activation, and lockout restrictions. A valid password may lead to an MFA challenge rather than a usable session. MFA secrets are encrypted; recovery codes are hashed. TOTP replay prevention tracks the last accepted time step. Redis challenges have independent consumption semantics: consuming a challenge cannot be undone by SQL rollback. The process-local `memory://` Redis substitute does not enforce TTLs or coordinate workers.

Employee records and login accounts are distinct. Provisioning links an eligible employee to a tenant-scoped invited account. Account tokens are stored as hashes. Invitation resend can issue another usable token without invalidating an earlier unexpired invitation; delivery failure therefore does not destroy the earlier link. Successful activation consumes outstanding account tokens and revokes sessions. Identity changes may invalidate tokens deliberately. Public errors stay generic even when audit records contain a more specific reason.

## Documents and native signing

Uploads validate file metadata and persist a checksum. New file writes register rollback cleanup. Retrieval authorizes the actor before reading a path confined to storage. Missing source files must be restored or re-uploaded; success must never be fabricated without a source PDF. DOCX conversion prepares a PDF source for signing; external conversion failures remain operational errors.

A signing request connects the document, requester, ordered recipients, fields, events, and artifacts. Field placement uses normalized page coordinates so browser zoom does not change persisted geometry. The server validates recipients and fields. Generated signatures use the official profile identity; typed, drawn, and uploaded inputs follow their respective validation paths. Consent and signing time are recorded with the submission, and required fields must be complete.

Lifecycle mutations lock and refresh the parent request before evaluating recipient state. Concurrent final signers and repeated submissions must converge on one completion artifact. A signed retry returns the existing receipt rather than replacing the original signature. Sequential requests activate the next recipient after the current step completes. Cancelled, expired, or otherwise closed requests reject new signatures.

Final rendering, artifact metadata, recipient completion, events, and in-app notifications belong to the signing transaction. Rendering/storage failure rolls these mutations back and removes newly written artifacts. Only after a valid final PDF exists can completion commit. Artifact checksums support integrity checks; they do not replace access control or establish a provider assurance level.

## Evidence, storage, and notifications

Native signing and external provider assurance are separate paths. Provider callbacks are verified and reconciled by event identity and state ordering. Duplicate/stale callbacks must not regress completed state. Provider evidence workers claim due or stale jobs with `FOR UPDATE SKIP LOCKED`, commit their leases, then download and validate provider artifacts. Retry scheduling and permanent validation failures are explicit evidence states. `backend/signature_evidence_worker.py` polls these services and handles termination between iterations.

Source uploads and evidence have separate storage helpers. Evidence can use local disk or S3, with checksums and cleanup for new uncommitted writes. Callers still authorize access. Local paths are not public URLs. A mocked S3 outage test is not proof of live bucket permissions, lifecycle configuration, or provider connectivity.

Notifications are database rows in the caller's transaction by default. Recipients must be active and tenant-compatible; platform users can receive their own tenant-scoped notifications. Internal action URLs prevent notification links from becoming arbitrary redirects. Email callbacks run after commit using captured values, then persist delivery status in a separate session. An SMTP error cannot undo an already committed workflow. These callbacks are best effort: process termination between commit and delivery can lose an email. There is no durable email outbox/retry worker yet.

## Other domain responsibilities

| Area | Main code and contract |
| --- | --- |
| People and departments | Employee, department, and access services coordinate identity, reporting lines, transfers, and account links. Route-level actor/tenant checks remain mandatory. |
| Leave | Policy service configures entitlement and governance; accrual service uses decimal days, eligibility/proration and ledger identity; leave service coordinates requests, approval and balance effects. Repeated accrual must not grant duplicate credit. |
| Attendance | Attendance routes/services own check-in/out and summaries; UI time presentation is separate from stored timestamps. |
| Goals | Goal services own lifecycle/check-ins; summary views derive progress rather than introducing another writable source of truth. |
| Onboarding | Templates, assignments, resources, attempts and video progress are related records. Training completion rules belong to backend services, not a browser playback event alone. |
| Employee experience | Home/settings routes assemble profile, essentials, events and branding under organization visibility rules. |
| Signing discussions/templates/seals | Separate services manage collaboration, reusable field configuration and seal artifacts. These do not bypass signing authorization or replace recipient consent. |
| Audit | Audit records explain actor/domain actions; external error messages must not expose internal diagnostics. |

## Frontend workflow responsibilities

`AuthContext` owns session presentation; `TenantContext` owns platform organization selection. `Form`, `formFeedback`, and `useFormDraft` coordinate validation, request ownership, pending state, feedback, dirty exits and revision-checked draft persistence. Saving a draft does not mean submitting a business mutation. Draft snapshots omit files and secret-like values; the server independently rejects unsafe payloads. Queued saves are serialized, and discard invalidates older queued writes. A conflicting revision should remain visible rather than overwrite another tab's newer draft.

`SignatureTask` separates task loading from PDF loading and preserves entered values on submission failure. The backend remains authoritative for closure and retry receipts. The PDF viewer copies binary input before worker transfer and cancels work on cleanup. Vite's PDF.js API alias and legacy worker must stay paired for browser compatibility. Field and seal editors use normalized geometry with parent-owned state.

`Modal` and the mobile `Sidebar` contain keyboard focus, restore focus and lock background scrolling. Nested table controls must not activate their parent row. Notifications update read-all state only after server success and offer retry on failure. Activation validation has explicit retry/sign-in recovery. Shared inputs and workflow feedback connect validation errors to controls; accessibility still needs real screen-reader/device testing beyond automated checks.

## Runtime, migrations, and CI

Configuration is loaded by `app/config.py`; production validates required settings. Bare `postgres://` and `postgresql://` URLs normalize to `postgresql+psycopg2://` to match the declared driver. Explicit driver URLs are preserved. `run.py` selects the configured environment; `wsgi.py` constructs production for Gunicorn. Alembic migrations are reviewed schema history; do not replace production migrations with `create_all()`.

Vercel builds the frontend. A production-like build uses `VITE_API_BASE_URL=/api`; Vercel routing forwards API traffic to Render. Render runs the backend Docker image, executes database upgrade before deployment, and uses `/ready` for dependency readiness. `/health` includes release metadata. The Render service root is `backend`, so frontend-only commits need not redeploy it. Check actual deployment metadata rather than inferring release state from GitHub merge status.

GitHub Actions separate backend, frontend, and browser acceptance jobs with path filters. Backend CI validates PostgreSQL migrations and application tests; concurrency fixtures require a disposable PostgreSQL URL. Frontend CI runs lint, unit/integration tests and build. Browser acceptance migrates/seeds isolated services and runs desktop/mobile Chromium. CI generates one fresh Base32 `DEMO_MFA_SECRET` into `GITHUB_ENV` for both seeding and Playwright. No production MFA credential belongs in this environment.

Tests cover behavior at different boundaries: SQLite application tests, real PostgreSQL locking/uniqueness tests, frontend integration tests, and browser journeys against seeded services. Intercepted browser responses cover recovery UI, not backend acceptance. Public production smoke checks establish runtime/assets/responsiveness only; authenticated production mutation testing requires a designated disposable account/data set.
