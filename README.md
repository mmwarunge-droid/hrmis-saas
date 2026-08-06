# Kinetic HR Platform


## Kinetic people experience

The Kinetic interface includes a BambooHR-inspired, people-first home workspace, people directory, org chart, department administration, bulk workforce transfers, calendar-led time off, document library, task center and a super-admin organization provisioning flow. See [`docs/KINETIC_REDESIGN.md`](docs/KINETIC_REDESIGN.md), [`PRODUCT_UI_UPGRADE.md`](PRODUCT_UI_UPGRADE.md), and [`DEPARTMENT_MANAGEMENT.md`](DEPARTMENT_MANAGEMENT.md) for the delivered scope and operating workflows.

A multi-tenant HRMIS SaaS platform designed as the digital operating layer for high-touch HR consulting services. The MVP covers employee system of record, secure documents, leave and attendance, onboarding, RBAC, audit logs, and tenant isolation.

## Architecture

- **Frontend:** React, Vite, Tailwind CSS, React Router, Context API, Axios.
- **Backend:** Flask application factory, Blueprints, SQLAlchemy, Alembic, JWT, RBAC decorators, service layer.
- **Database:** PostgreSQL with UUID primary keys, foreign keys, indexes, check constraints, soft deletes, and audit timestamps.
- **Deployment:** Vercel frontend, separately hosted Flask API, PostgreSQL, and GitHub Actions CI.

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
flask --app run.py db upgrade
flask --app run.py demo-seed
flask --app run.py run
```

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```


## Existing employee access

For a person already present in the People directory, open the employee record and choose **Provision access**. The workflow creates a tenant-scoped `EMPLOYEE` or `MANAGER` account, links it to the existing employee profile, and rolls back the entire operation if the email or employee link conflicts.

## Deterministic demo environment

`flask --app run.py demo-seed` creates the presentation-ready fictional dataset and is intentionally blocked in production. Reset only the managed demo tenants and accounts after a walkthrough:

```bash
cd backend
flask --app run.py demo-reset --yes --as-of 2026-08-06
flask --app run.py demo-status --as-of 2026-08-06
```

The convenience command `python seed.py` loads the same rich seed. See [`docs/DEMO_ENVIRONMENT.md`](docs/DEMO_ENVIRONMENT.md) for the account matrix, TOTP helper, baseline counts and screenshot checklist.

## Administrator provisioning

Provision the first production platform administrator through the one-time CLI workflow:

```bash
export BOOTSTRAP_ADMIN_EMAIL='admin@example.com'
export BOOTSTRAP_ADMIN_PASSWORD='use-a-password-manager-generated-password'
export BOOTSTRAP_ADMIN_FIRST_NAME='Platform'
export BOOTSTRAP_ADMIN_LAST_NAME='Administrator'
flask --app run.py bootstrap-admin
```

The command refuses to run after any user exists. Remove the bootstrap environment variables immediately after successful provisioning.

## Migration commands

```bash
cd backend
flask --app run.py db revision -m "describe change"
flask --app run.py db upgrade
flask --app run.py db downgrade -1
flask --app run.py db current
```

## Quality checks

```bash
cd backend
ruff check .
pytest --cov=app

cd ../frontend
npm run lint
npm test
VITE_API_BASE_URL=https://api.example.test/api npm run build
```

See `PRODUCTION_READINESS.md` for the staged hardening program.
