# HRMIS SaaS — Render + Vercel Live Deployment

## Production domain layout

Use sibling domains under one registrable domain:

- Frontend: `https://app.example.com`
- Backend: `https://api.example.com`

Replace `example.com` everywhere with your actual domain.

This layout is required by the current double-submit CSRF implementation. The browser frontend must read the CSRF cookie while the JWT cookies remain HttpOnly.

## Repository release

1. Merge `feat/production-readiness-step-2` into `main`.
2. Confirm GitHub Actions pass.
3. Deploy only from `main`.

## Render infrastructure

Use a Render Blueprint:

- Repository: `mmwarunge-droid/hrmis-saas`
- Branch: `main`
- Blueprint path: `backend/render.yaml`
- Region: Frankfurt for the web service, Postgres, and Key Value

The committed `backend/render.yaml` is the production Render Blueprint used during deployment.

### Values Render will prompt for

```dotenv
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
JWT_COOKIE_DOMAIN=.example.com
PASSWORD_RESET_URL=https://app.example.com/reset-password
EMAIL_VERIFICATION_URL=https://app.example.com/verify-email

MFA_ENCRYPTION_KEYS=<generated Fernet key>
MFA_RECOVERY_CODE_PEPPER=<generated independent random secret>

MAIL_FROM=no-reply@example.com
MAIL_SMTP_HOST=smtp.resend.com
MAIL_SMTP_USERNAME=resend
MAIL_SMTP_PASSWORD=<Resend API key>
```

Do not add quotation marks around the values in the Render dashboard.

### Generate MFA secrets locally

Run inside `backend/.venv`:

```bash
python - <<'PY'
import secrets
from cryptography.fernet import Fernet

print("MFA_ENCRYPTION_KEYS=" + Fernet.generate_key().decode())
print("MFA_RECOVERY_CODE_PEPPER=" + secrets.token_urlsafe(48))
PY
```

Store the output only in Render. Do not commit it and do not paste it into chat.

### Render first-deploy checks

```bash
curl -fsS https://api.example.com/health
curl -fsS https://api.example.com/ready
```

Both must return a successful JSON response.

### Bootstrap the first administrator

Temporarily add these Render environment variables:

```dotenv
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=<strong unique password>
BOOTSTRAP_ADMIN_FIRST_NAME=Platform
BOOTSTRAP_ADMIN_LAST_NAME=Administrator
```

Open the Render Shell and run:

```bash
flask --app run.py bootstrap-admin
```

After it succeeds, delete all four `BOOTSTRAP_ADMIN_*` variables and redeploy.

## Render custom domain

1. Open the `hrmis-saas-api` web service.
2. Go to **Settings → Custom Domains**.
3. Add `api.example.com`.
4. Create the DNS record Render displays.
5. Verify the domain and wait for TLS.
6. Keep the `onrender.com` URL enabled until production verification is complete.

## SMTP with Resend

1. Add and verify `example.com` in Resend.
2. Create a sending API key.
3. Configure the Render variables shown above.
4. Use port `587` with TLS.
5. Test both password-reset and verification emails.

## Vercel frontend

Import the same GitHub repository as a new Vercel project.

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Node.js Version | 22.x |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Production Branch | `main` |

Production environment variables:

```dotenv
VITE_API_BASE_URL=https://api.example.com/api
VITE_APP_NAME=HRMIS
```

The committed `frontend/vercel.json` already provides the SPA rewrite and security headers.

## Vercel custom domain

1. Open the Vercel project.
2. Go to **Settings → Domains**.
3. Add `app.example.com`.
4. Create the exact DNS record Vercel displays.
5. Wait for verification and TLS.
6. Redeploy production after setting the final environment variables.

## Final backend values

Confirm these exact values in Render:

```dotenv
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
JWT_COOKIE_DOMAIN=.example.com
JWT_COOKIE_SAMESITE=Lax
PASSWORD_RESET_URL=https://app.example.com/reset-password
EMAIL_VERIFICATION_URL=https://app.example.com/verify-email
```

Do not add a trailing slash.

## Production smoke test

1. Open `https://app.example.com`.
2. Sign in with the bootstrap administrator.
3. Complete MFA enrollment and save the recovery codes securely.
4. Refresh the browser and confirm the session remains authenticated.
5. Create a tenant administrator.
6. Test an authenticated POST operation.
7. Request and complete email verification.
8. Request and complete password reset.
9. Upload a document.
10. Redeploy the API and confirm the uploaded document remains available.
11. Confirm logout, logout-all, and individual session revocation.
12. Confirm `/health` and `/ready` remain successful.

## Browser cookie verification

In browser developer tools, inspect cookies for `.example.com`.

Expected:

- `access_token_cookie`: Secure, HttpOnly, path `/api/`
- `refresh_token_cookie`: Secure, HttpOnly, path `/api/auth/refresh`
- `csrf_access_token`: Secure, readable by JavaScript, path `/`
- `csrf_refresh_token`: Secure, readable by JavaScript, path `/`

The JWT values must never appear in Local Storage or Session Storage.

## Preview deployments

Default Vercel preview URLs use `vercel.app`, so they do not share the `.example.com` cookie domain. Treat ordinary previews as build/UI previews only.

For fully authenticated staging, deploy:

- `https://staging.example.com` on Vercel
- `https://api-staging.example.com` on Render
- A separate staging Postgres and Key Value instance

Never point untrusted pull-request previews at the production API.

## Operational limitations

The attached Render persistent disk is required by the current local document-storage implementation. It limits the API to one service instance and prevents zero-downtime deploys. Before scaling, migrate document storage to private S3-compatible object storage and use signed delivery URLs.
