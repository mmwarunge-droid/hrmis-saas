import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

const here = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(here, '.auth', 'employee.json');

async function existingStateIsUsable(browser, baseURL) {
  try {
    await fs.access(authFile);
  } catch {
    return false;
  }

  const context = await browser.newContext({
    baseURL,
    storageState: authFile,
  });

  try {
    const page = await context.newPage();
    await page.goto('/dashboard');

    const authStatus = await page.evaluate(async () => {
      const response = await fetch(
        'http://localhost:5000/api/auth/me',
        { credentials: 'include' },
      );
      return response.status;
    });

    await page.waitForTimeout(500);

    return (
      authStatus === 200
      && new URL(page.url()).pathname === '/dashboard'
    );
  } catch {
    return false;
  } finally {
    await context.close();
  }
}

export default async function globalSetup() {
  const baseURL =
    process.env.E2E_BASE_URL || 'http://localhost:5173';
  const email =
    process.env.E2E_DEMO_EMAIL || 'employee@kinetic.demo';
  const password = process.env.E2E_DEMO_PASSWORD;

  const browser = await chromium.launch();

  try {
    await fs.mkdir(path.dirname(authFile), { recursive: true });

    if (await existingStateIsUsable(browser, baseURL)) {
      console.log('Reusing valid browser acceptance session.');
      return;
    }

    if (!password) {
      throw new Error(
        'E2E_DEMO_PASSWORD must be configured when no valid '
          + 'browser acceptance session exists.',
      );
    }

    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();

    try {
      await page.goto('/login');
      await page.getByLabel('Work email').fill(email);
      await page.getByLabel('Password').fill(password);

      const loginResponsePromise = page.waitForResponse(
        (response) =>
          response.url().includes('/api/auth/login')
          && response.request().method() === 'POST',
      );

      await page
        .getByRole('button', { name: /sign in/i })
        .click();

      const loginResponse = await loginResponsePromise;

      if (loginResponse.status() !== 200) {
        throw new Error(
          `Demo browser login returned HTTP ${loginResponse.status()}`,
        );
      }

      await page.waitForURL(
        (url) => url.pathname !== '/login',
        { timeout: 10_000 },
      );

      await page.goto('/dashboard');
      await page.waitForURL(
        (url) => url.pathname === '/dashboard',
        { timeout: 10_000 },
      );

      const authStatus = await page.evaluate(async () => {
        const response = await fetch(
          'http://localhost:5000/api/auth/me',
          { credentials: 'include' },
        );
        return response.status;
      });

      if (authStatus !== 200) {
        throw new Error(
          `Authenticated session check returned HTTP ${authStatus}`,
        );
      }

      await page.waitForTimeout(500);

      if (new URL(page.url()).pathname !== '/dashboard') {
        throw new Error(
          `Authenticated session redirected to ${page.url()}`,
        );
      }

      await context.storageState({ path: authFile });
      console.log('Browser acceptance session created.');
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}
