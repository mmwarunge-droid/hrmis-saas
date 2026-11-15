// No intercepted APIs: use only the designated disposable local acceptance stack.
import { readFileSync } from 'node:fs';
import { createHmac } from 'node:crypto';
import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const apiBase = 'http://localhost:5059/api';
function otp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = [...secret.replace(/=+$/, '')]
    .map((c) => alphabet.indexOf(c).toString(2).padStart(5, '0'))
    .join('');
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac('sha1', key).update(counter).digest();
  const offset = digest.at(-1) & 15;
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, '0');
}
async function login(page, email, mfa) {
  await page.goto('/login');
  await page.getByLabel('Work email').fill(email);
  await page
    .getByLabel('Password', { exact: true })
    .fill(process.env.ORG_TEST_PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  if (mfa) {
    await page
      .getByLabel('Authenticator or recovery code')
      .fill(otp(process.env.DEMO_MFA_SECRET));
    await page.getByRole('button', { name: 'Verify', exact: true }).click();
  }
  await expect(page).not.toHaveURL(/login|mfa/);
}
async function api(context, path, method = 'GET', data) {
  const cookies = await context.cookies(apiBase);
  const csrf = cookies.find(
    (cookie) => cookie.name === 'csrf_access_token',
  )?.value;
  return context.request.fetch(apiBase + path, {
    method,
    data,
    headers: csrf ? { 'X-CSRF-TOKEN': csrf } : {},
  });
}

test('authenticated PostgreSQL hierarchy, directory, editing, tenant boundaries and mobile controls', async ({
  browser,
}) => {
  expect(process.env.ORG_TEST_PASSWORD).toBeTruthy();
  const ids = JSON.parse(readFileSync(process.env.ORG_TEST_FIXTURE, 'utf8'));
  const context = await browser.newContext({
    baseURL: 'http://localhost:5189',
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await login(page, 'admin-0@org-chart.test', true);
  const start = Date.now();
  const response = await api(context, '/employees/org-chart?format=flat');
  expect(response.status()).toBe(200);
  const chart = (await response.json()).data;
  expect(chart.items).toHaveLength(1000);
  expect(
    chart.items.find((p) => p.id === ids.employees[0]).indirect_report_count,
  ).toBe(994);
  expect(JSON.stringify(chart)).not.toContain('OtherTenant');
  expect(chart.items[0]).not.toHaveProperty('phone');
  expect(chart.items[0]).not.toHaveProperty('date_of_birth');
  console.log(
    `Authenticated 1000-person API response: ${Date.now() - start} ms`,
  );
  const forged = await api(
    context,
    `/employees/org-chart?format=flat&tenant_id=${ids.tenants[1]}`,
  );
  expect((await forged.json()).data.items).toHaveLength(1000);
  expect((await api(context, `/employees/${ids.outsider}`)).status()).toBe(404);
  expect(
    (
      await api(context, `/employees/${ids.employees[2]}`, 'PATCH', {
        manager_id: ids.outsider,
      })
    ).status(),
  ).toBe(400);
  await page.goto('/employees');
  await expect(
    page.getByRole('heading', { name: 'People directory' }),
  ).toBeVisible();
  await page.goto(`/employees/${ids.employees[2]}`);
  await page.getByRole('button', { name: 'Edit employee' }).click();
  await page.getByLabel('Work location', { exact: true }).fill('Kisumu');
  await page
    .getByRole('button', { name: 'Update employee', exact: true })
    .click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  expect(
    (await (await api(context, `/employees/${ids.employees[2]}`)).json()).data
      .work_location,
  ).toBe('Kisumu');
  await page.goto('/org-chart');
  await page
    .getByPlaceholder('Search people, roles or departments')
    .fill('Carol');
  await page
    .getByRole('button', { name: 'Carol Acceptance · Specialist', exact: true })
    .click();
  const panel = page.getByRole('complementary', { name: 'Employee details' });
  await expect(panel).toContainText('Kisumu');
  await page.getByRole('button', { name: 'Change reporting manager' }).click();
  await page.getByLabel('New reporting manager').selectOption(ids.employees[1]);
  const mutation = page.waitForResponse(
    (r) =>
      r.request().method() === 'PATCH' &&
      r.url().endsWith(`/employees/${ids.employees[2]}`),
  );
  await page
    .getByRole('button', { name: 'Confirm change', exact: true })
    .click();
  expect((await mutation).status()).toBe(200);
  await expect(page.getByRole('dialog')).not.toBeVisible();
  const changed = (
    await (await api(context, '/employees/org-chart?format=flat')).json()
  ).data;
  expect(changed.items.find((p) => p.id === ids.employees[2]).manager_id).toBe(
    ids.employees[1],
  );
  expect(
    changed.items.find((p) => p.id === ids.employees[1]).direct_report_count,
  ).toBe(6);
  expect(
    (
      await api(context, `/employees/${ids.employees[0]}`, 'PATCH', {
        manager_id: ids.employees[2],
      })
    ).status(),
  ).toBe(400);
  const history = await api(
    context,
    `/employees/${ids.employees[2]}/job-history`,
  );
  expect(await history.text()).toContain(ids.employees[1]);
  await page.getByText('View settings and filters', { exact: true }).click();
  await page.getByLabel('Layout', { exact: true }).selectOption('stacked');
  await page.getByLabel('Filter Work location').selectOption('Kisumu');
  await expect(page.getByText(/1 matching employees/)).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await panel.focus();
  await page.keyboard.press('Escape');
  await expect(panel).not.toBeVisible();
  const canvas = page.getByRole('region', {
    name: 'Organization chart canvas',
  });
  await canvas.focus();
  await page.keyboard.press('ArrowDown');
  expect(await canvas.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  const axe = await new AxeBuilder({ page }).include('main').analyze();
  expect(
    axe.violations.filter((v) => ['serious', 'critical'].includes(v.impact)),
  ).toEqual([]);
  await page.screenshot({
    path: '/tmp/hrmis-org-integration/desktop.png',
    fullPage: true,
  });
  const mobile = await browser.newContext({
    baseURL: 'http://localhost:5189',
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    storageState: await context.storageState(),
  });
  const phone = await mobile.newPage();
  phone.on('pageerror', (error) => errors.push(error.message));
  await phone.goto(`/org-chart?employee=${ids.employees[2]}`);
  await expect(
    phone.getByRole('complementary', { name: 'Employee details' }),
  ).toContainText('Carol Acceptance');
  await phone.getByRole('button', { name: 'Close employee details' }).click();
  await phone
    .getByRole('button', { name: 'Zoom out organization chart' })
    .click();
  await expect(phone.getByText('90%', { exact: true })).toBeVisible();
  expect(
    await phone.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  const mobileAxe = await new AxeBuilder({ page: phone })
    .include('main')
    .analyze();
  expect(
    mobileAxe.violations.filter((v) => ['serious', 'critical'].includes(v.impact)),
  ).toEqual([]);
  await phone.evaluate(() => {
    document.activeElement?.blur();
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  });
  await phone.screenshot({
    path: '/tmp/hrmis-org-integration/mobile.png',
    fullPage: true,
  });
  const second = await browser.newContext({ baseURL: 'http://localhost:5189' });
  const secondPage = await second.newPage();
  secondPage.on('pageerror', (error) => errors.push(error.message));
  await login(secondPage, 'admin-1@org-chart.test', true);
  expect(
    (await (await api(second, '/employees/org-chart?format=flat')).json()).data
      .items,
  ).toHaveLength(1);
  expect((await api(second, `/employees/${ids.employees[0]}`)).status()).toBe(
    404,
  );
  const readOnly = await browser.newContext({
    baseURL: 'http://localhost:5189',
  });
  const reader = await readOnly.newPage();
  reader.on('pageerror', (error) => errors.push(error.message));
  await login(reader, 'reader@org-chart.test', false);
  await reader.goto(`/org-chart?employee=${ids.employees[2]}`);
  await expect(
    reader.getByRole('complementary', { name: 'Employee details' }),
  ).toBeVisible();
  await expect(
    reader.getByRole('button', { name: 'Change reporting manager' }),
  ).toHaveCount(0);
  expect(
    (
      await api(readOnly, `/employees/${ids.employees[2]}`, 'PATCH', {
        manager_id: null,
      })
    ).status(),
  ).toBe(403);
  expect(errors).toEqual([]);
  await Promise.all([
    context.close(),
    mobile.close(),
    second.close(),
    readOnly.close(),
  ]);
});
