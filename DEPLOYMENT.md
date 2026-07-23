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
REDIS_URL=rediss://...
REDIS_KEY_PREFIX=hrmis:auth
MFA_REQUIRED_ROLES=SUPER_ADMIN,CLIENT_ADMIN
MFA_ENCRYPTION_KEYS=<comma-separated Fernet keys, newest first>
MFA_RECOVERY_CODE_PEPPER=<different random value of at least 32 characters>
MFA_TOTP_ISSUER=HRMIS
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
API_PREFIX=/api
UPLOAD_FOLDER=/var/data/uploads
MAX_CONTENT_LENGTH=10485760
TOKEN_EXPIRY_MINUTES=60
REFRESH_TOKEN_EXPIRY_DAYS=14
JWT_COOKIE_SAMESITE=Lax
JWT_COOKIE_DOMAIN=.example.com
AUTH_MAX_FAILED_ATTEMPTS=5
AUTH_FAILURE_WINDOW_MINUTES=15
AUTH_LOCKOUT_MINUTES=15
AUTH_SUSPICIOUS_LOGIN_ENABLED=true
TRUST_PROXY_HEADERS=false
PASSWORD_RESET_TOKEN_MINUTES=30
EMAIL_VERIFICATION_TOKEN_HOURS=24
PASSWORD_RESET_URL=https://app.example.com/reset-password
EMAIL_VERIFICATION_URL=https://app.example.com/verify-email
MAIL_TRANSPORT=smtp
MAIL_FROM=no-reply@example.com
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USERNAME=<smtp username>
MAIL_SMTP_PASSWORD=<smtp secret>
MAIL_SMTP_USE_TLS=true
MAIL_SMTP_TIMEOUT_SECONDS=10
RATELIMIT_DEFAULT=200 per day;50 per hour
RATELIMIT_STORAGE_URI=memory://
```

`RATELIMIT_STORAGE_URI=memory://` is acceptable only during the current foundation phase. Replace it with Redis before production launch.

Generate an MFA encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the newest key first in `MFA_ENCRYPTION_KEYS`. Keep previous keys during rotation so existing TOTP secrets remain decryptable. `MFA_RECOVERY_CODE_PEPPER` must be a separate random secret and must not be rotated without invalidating all existing recovery codes.

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

- Redis-backed distributed rate limiting.
- Private object storage and secure document delivery.
- PostgreSQL integration tests rather than SQLite-only application tests.
- Monitoring, error tracking, backups, restore drills, and security alerting.


## Authentication session store

Set `REDIS_URL` to a private Redis instance. Production readiness checks require both PostgreSQL and Redis connectivity. Redis must use persistence and must not be exposed to the public internet.

## Authentication lockout and audit controls

Configure `AUTH_MAX_FAILED_ATTEMPTS`, `AUTH_FAILURE_WINDOW_MINUTES`, and `AUTH_LOCKOUT_MINUTES` for the deployment risk profile. Keep `AUTH_SUSPICIOUS_LOGIN_ENABLED=true` to record new-network and new-user-agent risk flags. `TRUST_PROXY_HEADERS` must remain false unless the application is behind a trusted reverse proxy that strips and overwrites `X-Forwarded-For`; enabling it behind an untrusted proxy permits client IP spoofing. Authentication audit records store reduced IP networks and keyed user-agent or identifier fingerprints rather than raw identifiers.

## Account recovery and email verification

Password reset and email verification tokens are random, single use, stored only as hashes, and expire according to `PASSWORD_RESET_TOKEN_MINUTES` and `EMAIL_VERIFICATION_TOKEN_HOURS`. Configure `PASSWORD_RESET_URL` and `EMAIL_VERIFICATION_URL` as HTTPS frontend routes that read the URL-fragment token and submit it to the API with `POST`; do not consume account tokens from `GET` links because security scanners and mail clients may prefetch them. URL fragments keep the raw token out of HTTP request lines and referrer headers.

Development may use `MAIL_TRANSPORT=console`, which writes the complete message and one-time link to backend logs. Production validation requires `MAIL_TRANSPORT=smtp`, `MAIL_FROM`, and `MAIL_SMTP_HOST`. Protect SMTP credentials as secrets, enable TLS, and avoid logging email bodies in production. A successful password reset revokes all active sessions for the account.
