# Deployment

## Backend and PostgreSQL

The Flask API must be deployed separately from Vercel because document storage and long-running backend responsibilities require a persistent backend environment.

Required production variables:

```dotenv
APP_ENV=production
FLASK_ENV=production
SECRET_KEY=<different random value of at least 32 characters>
JWT_SECRET_KEY=<different random value of at least 32 characters>
DATABASE_URL=postgresql://...
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
API_PREFIX=/api
UPLOAD_FOLDER=/var/data/uploads
MAX_CONTENT_LENGTH=10485760
TOKEN_EXPIRY_MINUTES=60
REFRESH_TOKEN_EXPIRY_DAYS=14
JWT_COOKIE_SAMESITE=Lax
JWT_COOKIE_DOMAIN=.example.com
RATELIMIT_DEFAULT=200 per day;50 per hour
RATELIMIT_STORAGE_URI=memory://
```

`RATELIMIT_STORAGE_URI=memory://` is acceptable only during the current foundation phase. Replace it with Redis before production launch.

Build and release commands:

```bash
pip install -r requirements.txt
flask --app run.py db upgrade
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 3 --timeout 120
```

Health endpoints:

- `GET /health` — process liveness.
- `GET /ready` — database readiness.

After the first migration, provision the initial administrator with `flask --app run.py bootstrap-admin`. Never use `python seed.py` in production.

## Vercel frontend

Create a Vercel project with:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Node.js | 22.x, at least 22.12 |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Production Branch | `main` |

Required environment variables for every Vercel environment:

```dotenv
VITE_API_BASE_URL=https://api.example.com/api
VITE_APP_NAME=Your Company HRMIS
```

Use a separate staging API URL for Preview and Staging deployments. A production build fails intentionally when `VITE_API_BASE_URL` is missing.

The committed `frontend/vercel.json` configures the SPA rewrite, immutable asset caching, and baseline security headers. Tighten its `connect-src` Content Security Policy to the exact production and staging API domains once those domains are selected.

## Production release sequence

1. Deploy PostgreSQL and the backend service.
2. Run Alembic migrations.
3. Verify `/health` and `/ready`.
4. Provision the first `SUPER_ADMIN` with the CLI command.
5. Remove all bootstrap environment variables.
6. Configure exact backend CORS origins and cookie credentials.
7. Configure Vercel Production, Preview, and Staging variables.
8. Deploy the frontend from a protected `main` branch.
9. Run login, tenant isolation, employee CRUD, document, leave, onboarding, and audit-log smoke tests.

## Remaining launch blockers

- Redis-backed rate limiting and JWT revocation.
- Private object storage and secure document delivery.
- PostgreSQL integration tests rather than SQLite-only application tests.
- Monitoring, error tracking, backups, restore drills, and security alerting.


## Authentication session store

Set `REDIS_URL` to a private Redis instance. Production readiness checks require both PostgreSQL and Redis connectivity. Redis must use persistence and must not be exposed to the public internet.
