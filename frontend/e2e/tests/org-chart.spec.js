// Synthetic API fixtures: browser interaction coverage, not live backend acceptance.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const people = Array.from({ length: 1000 }, (_, i) => ({
  id: `person-${i}`,
  full_name: `Colleague ${i}`,
  employee_number: `EMP-${i}`,
  manager_id: i ? `person-${Math.floor((i - 1) / 5)}` : null,
  job_title: i ? 'Team specialist' : 'Executive director',
  department_name: i % 2 ? 'Engineering' : 'People',
  work_location: 'Nairobi',
  employment_status: 'active',
  email: `person${i}@example.test`,
  hire_date: '2020-01-01',
  direct_report_count: Math.min(5, Math.max(0, 1000 - (i * 5 + 1))),
  indirect_report_count: 0,
}));

for (let i = people.length - 1; i > 0; i--) {
  const parent = people[Math.floor((i - 1) / 5)];
  parent.indirect_report_count +=
    people[i].direct_report_count + people[i].indirect_report_count;
}

test('explores a large organization with responsive controls and no background polling', async ({
  page,
}, testInfo) => {
  const errors = [];
  let requests = 0;
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    let data = { items: [], unread_count: 0 };
    if (path === '/api/auth/me')
      data = {
        id: 'user',
        tenant_id: 'tenant',
        first_name: 'Test',
        last_name: 'Admin',
        email: 'admin@example.test',
        roles: ['CLIENT_ADMIN'],
        permissions: ['employee:read', 'employee:update'],
      };
    if (path === '/api/employees/org-chart') {
      requests++;
      data = {
        items: people,
        meta: { total: 1000, manager_count: 200 },
        integrity_issues: [],
      };
    }
    await route.fulfill({ json: { success: true, data } });
  });
  await page.goto('/org-chart');
  await expect(
    page.getByRole('button', { name: 'View Colleague 0', exact: true }),
  ).toBeVisible();
  await page
    .getByPlaceholder('Search people, roles or departments')
    .fill('Colleague 999');
  await page
    .getByRole('button', {
      name: 'Colleague 999 · Team specialist',
      exact: true,
    })
    .click();
  await expect(
    page.getByRole('complementary', { name: 'Employee details' }),
  ).toContainText('Colleague 999');
  await expect(
    page.getByRole('button', { name: 'View Colleague 999', exact: true }),
  ).toBeAttached();
  await page.getByText('View settings and filters', { exact: true }).click();
  await page.getByLabel('Layout', { exact: true }).selectOption('stacked');
  await page.getByRole('button', { name: 'Focus selected' }).click();
  await page.getByLabel('Color cards by').selectOption('department_name');
  await expect(page.getByLabel('Color legend')).toContainText('Engineering');
  await page.getByRole('button', { name: 'Close employee details' }).click();
  await page.getByLabel('Filter Department').selectOption('Engineering');
  await expect(
    page.getByText('500 matching employees', { exact: false }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await page
    .getByRole('button', { name: 'Zoom out organization chart' })
    .click();
  await expect(page.getByText('90%', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restore default view' }).click();
  const geometry = await page.evaluate(() => ({
    width: innerWidth,
    page: document.documentElement.scrollWidth,
    cards: document.querySelectorAll('article[aria-label$="employee card"]')
      .length,
  }));
  expect(geometry.page).toBeLessThanOrEqual(geometry.width + 1);
  expect(geometry.cards).toBeLessThan(100);
  expect(errors).toEqual([]);
  expect(requests).toBeLessThanOrEqual(2); // React development StrictMode can initiate twice.
  const axe = await new AxeBuilder({ page }).include('main').analyze();
  expect(
    axe.violations.filter((v) => ['serious', 'critical'].includes(v.impact)),
  ).toEqual([]);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.screenshot({
    path: `/tmp/hrmis-org-chart-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
