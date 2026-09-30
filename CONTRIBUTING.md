# Contributing to Kinetic

Read [the architecture guide](docs/DEVELOPER_ARCHITECTURE.md) before changing account, tenant, or signing workflows. Use a branch from current `main` (`fix/...`, `feat/...`, or `docs/...`); keep functional corrections separate from documentation commits.

## Local environment

Use Python 3.11 or 3.12, Node 22 (at least 22.13, below 23), PostgreSQL 16 and Redis 7. Install backend dependencies in a virtual environment and frontend dependencies with the committed lockfile. Start from `backend/.env.example` and `frontend/.env.example`; set local database, Redis, CORS and frontend URLs before migrations. Never copy production secrets into a development fixture. The backend defaults to SQLite for simple development; use PostgreSQL for migrations and concurrency acceptance.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env for your disposable local services first.
flask --app run.py db upgrade
flask --app run.py demo-seed
flask --app run.py run --port 5000
```

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Demo seeding is blocked in production. See [the demo guide](docs/DEMO_ENVIRONMENT.md) for managed data/reset semantics. For MFA browser testing, export a freshly generated disposable `DEMO_MFA_SECRET` before seeding and pass that exact value to Playwright; follow [the E2E README](frontend/e2e/README.md). Do not use a committed seed or a production MFA secret. Never run document-upload/signing acceptance against ordinary production records.

## Validation

From `backend` with the virtual environment active:

```bash
ruff check .
python -m compileall -q app run.py wsgi.py signature_evidence_worker.py
APP_ENV=testing pytest --cov=app
```

The standard application fixture uses in-memory SQLite. PostgreSQL concurrency tests skip unless `HRMIS_PG_TEST_URL` is set. Point it only at a dedicated disposable database: fixtures create/drop tables and records. Do not share that database with a running browser seed or another test process. First validate migrations with `APP_ENV=development DATABASE_URL=... flask --app run.py db upgrade`, then run the full suite with `HRMIS_PG_TEST_URL` set. A green SQLite run alone does not validate PostgreSQL row locks or concurrent uniqueness.

From `frontend`:

```bash
npm run lint
npm test -- --maxWorkers=2
VITE_API_BASE_URL=/api npm run build
```

From `frontend/e2e`, install with `npm ci --ignore-scripts`, install Chromium with `npm run install:browsers`, and run `npm test` against isolated API/frontend services. Use fresh ignored authentication state and a distinct artifact directory for each acceptance run. Avoid simultaneous suites sharing browser output or a mutable seed. The browser workflow is the executable reference for service startup and per-run MFA generation.

Run `git diff --check` before committing. Inspect staged paths: no `.env`, tokens, MFA seeds, auth state, screenshots, test reports, coverage output, temporary scripts or generated builds belong in the commit.

## Changes and review

Migrations live in `backend/migrations`. Review generated revisions and test upgrade on disposable PostgreSQL; do not use `create_all()` as deployment migration tooling. Document non-obvious transformations and compatibility requirements without annotating generated boilerplate. Keep PostgreSQL URL normalization aligned with the declared psycopg2 driver.

Backend authorization is mandatory even when frontend controls are hidden. Scope tenant data before pagination and test cross-tenant/cross-user denial. Account work needs invitation resend/activation, session, MFA and generic-error regressions as applicable. Signing work needs real PDF upload/rendering, sequential completion, closed-state rejection, idempotent retries, concurrent final signers, rollback/storage failure, notification and artifact checks. Preserve consent text unless a separately reviewed requirement changes it.

Explain responsibility and contracts in module comments. Use docstrings/JSDoc for non-obvious public behavior, callbacks, I/O, locking, commit ownership, errors and retry assumptions. Avoid comments that merely narrate syntax. If a comment contradicts behavior, inspect the implementation and tests before correcting it. Keep legal/product copy distinct from developer notes.

PR descriptions should state the problem and resulting behavior, documentation scope, separate functional fixes, actual test results, and known limits. Do not report old audit counts as a fresh run. Required CI must finish green before merge. Follow [the production runbook](docs/PRODUCTION_DEMO_RUNBOOK.md) for release observation and rollback; verify deployment SHA, not just a successful build badge. Authenticated production mutation checks require an explicitly designated disposable account/data set.
