import { expect, test } from '@playwright/test';
import { mockProfile } from './fixtures.js';
import { verify } from './geometry.js';
for (const width of [390, 1440]) {
  test(`combined PR78 org chart opens corrected employee profile at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    const person = await mockProfile(page);
    await page.route((url) => url.pathname === '/api/employees/org-chart', route => route.fulfill({ json: { data: { items: [{ ...person, manager_id: null, direct_report_count: 0, indirect_report_count: 0 }], meta: { total: 1, manager_count: 0, root_count: 1, max_depth: 1 }, integrity_issues: [], vacancies: [] } } }));
    await page.goto('/org-chart?employee=synthetic-person');
    const panel = page.getByRole('complementary', { name: 'Employee details' });
    await expect(panel).toContainText('Mary Example');
    await panel.getByRole('link', { name: 'View employee profile' }).click();
    await expect(page).toHaveURL(/employees\/synthetic-person/);
    const header = await verify(page);
    await expect(header.getByRole('heading', { name: 'Mary Example' })).toBeVisible();
    await expect(header.getByRole('button', { name: 'Edit employee' })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

// Reproduce the cross-frame measurement hazard without disabling smooth scrolling.
test('profile geometry remains strict during smooth scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  await mockProfile(page);
  await page.goto('/employees/synthetic-person');
  await verify(page);
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' }));
  await verify(page);
  // A real overlap must still fail after layout settles.
  await page.locator('[data-profile-identity]').evaluate(el => { el.style.transform = 'translateY(-200px)'; });
  await expect(verify(page)).rejects.toThrow(/toBeGreaterThanOrEqual/);
});

test('layout readiness has a bounded diagnostic failure for ongoing animation', async ({ page }) => {
  await mockProfile(page);
  await page.goto('/employees/synthetic-person');
  await verify(page);
  await page.locator('.profile-header').evaluate(el => {
    el.animate([{ transform: 'translateY(0)' }, { transform: 'translateY(5px)' }], { duration: 1000, iterations: Infinity });
  });
  await expect(verify(page, { layoutTimeout: 200 })).rejects.toThrow(/Profile layout did not settle:.*runningAnimations.*current/);
});
