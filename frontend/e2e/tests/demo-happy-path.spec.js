import { expect, test } from '@playwright/test';

async function clickVisible(locator) {
  const count = await locator.count();

  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);

    if (await candidate.isVisible()) {
      await candidate.click();
      return;
    }
  }

  throw new Error('No visible navigation target was found.');
}

async function openPrimaryNavigationLink(page, name) {
  const links = page.getByRole('link', { name });

  for (let index = 0; index < await links.count(); index += 1) {
    if (await links.nth(index).isVisible()) {
      await links.nth(index).click();
      return;
    }
  }

  await page
    .getByRole('button', { name: /open navigation/i })
    .click();

  await expect(
    page.getByRole('button', { name: /close navigation/i }),
  ).toBeVisible();

  await clickVisible(
    page.getByRole('link', { name }),
  );
}

test.beforeEach(async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/dashboard\/?$/);
});

test(
  'employee can navigate core self-service workflows',
  async ({ page }) => {
    await expect(
      page.getByRole('heading', { level: 1 }),
    ).toBeVisible();

    await openPrimaryNavigationLink(page, /time off/i);
    await expect(page).toHaveURL(/\/leave/);
    await expect(
      page.getByRole('heading', { level: 1 }),
    ).toContainText(/time off/i);

    await openPrimaryNavigationLink(page, /attendance/i);
    await expect(page).toHaveURL(/\/attendance/);

    await openPrimaryNavigationLink(page, /goals & kpis/i);
    await expect(page).toHaveURL(/\/goals/);
    await expect(
      page.getByRole('heading', { name: /goals & kpis/i }),
    ).toBeVisible();
  },
);

test(
  'unknown route presents a useful recovery page',
  async ({ page }) => {
    await page.goto('/route-that-does-not-exist');

    await expect(
      page.getByRole(
        'heading',
        { name: /page is not available/i },
      ),
    ).toBeVisible();

    await expect(
      page.getByRole('link', { name: /open home/i }),
    ).toBeVisible();
  },
);
