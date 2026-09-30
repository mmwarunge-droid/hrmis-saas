# Browser acceptance suite

This isolated Playwright project validates the deployed or locally running Kinetic SPA without changing the main frontend dependency lock.

```bash
cd frontend/e2e
npm ci --ignore-scripts
npm run install:browsers
E2E_BASE_URL=http://127.0.0.1:5173 \
E2E_DEMO_PASSWORD='your-local-demo-password' \
DEMO_MFA_SECRET='the-same-disposable-secret-used-by-demo-seed' \
npm test
```

Use only a disposable demo account. The suite uploads and signs documents in addition to login, navigation and accessibility checks; it does not reset the database. Never run it against real production HR data.

Set `DEMO_MFA_SECRET` before seeding the acceptance database and pass that same value to Playwright. CI defines it once for both processes. `E2E_DEMO_MFA_SECRET` remains a compatibility override when `DEMO_MFA_SECRET` is absent; there is no hardcoded browser fallback. These values are disposable demo credentials, never production MFA credentials.
