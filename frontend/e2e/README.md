# Browser acceptance suite

This isolated Playwright project validates the deployed or locally running Kinetic SPA without changing the main frontend dependency lock.

```bash
cd frontend/e2e
npm install
npm run install:browsers
E2E_BASE_URL=http://127.0.0.1:5173 \
E2E_DEMO_PASSWORD='your-local-demo-password' \
npm test
```

Use only a disposable demo account. The suite performs login, navigation and accessibility checks; it does not reset the database.
