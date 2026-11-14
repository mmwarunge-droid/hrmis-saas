import { expect, test } from '@playwright/test';
import { verify } from './geometry.js';
import AxeBuilder from '@axe-core/playwright';
import { mockProfile, coverImage, avatarImage } from './fixtures.js';

const widths = [320, 390, 768, 1024, 1440, 1920];
const variants = [
  { label: 'default', data: {} },
  { label: 'long', data: { full_name: 'Mary Example with a very long multi-part family name and preferred professional name', job_title: 'Senior Director of People Operations, Organizational Development and International Employee Experience', department_name: 'People Operations and International Organizational Development' } },
  { label: 'unbroken', data: { full_name: 'LongName'.repeat(18), employment_status: 'probation' } },
  { label: 'empty', data: { full_name: 'Li', job_title: null, department_id: null, department_name: null, employment_status: 'inactive' }, readOnly: true },
  { label: 'custom', data: { profile_photo_url: avatarImage, profile_cover_url: coverImage } },
  { label: 'tenant', data: {}, tenantCover: coverImage },
];

for (const path of ['/employees/synthetic-person', '/profile']) {
  for (const width of widths) {
    test(`${path} identity stays below cover at ${width}px across content and branding variants`, async ({ page }) => {
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.setViewportSize({ width, height: 1000 });
      for (const variant of variants) {
        await page.unrouteAll();
        await mockProfile(page, variant.data, variant.readOnly, variant.tenantCover);
        await page.goto(path);
        const header = await verify(page);
        await expect(header.locator('[data-profile-identity]').getByText(variant.data.employment_status || 'active', { exact: true })).toBeVisible();
        if (path.startsWith('/employees')) {
          await expect(header.getByRole('button', { name: 'Edit employee' })).toHaveCount(variant.readOnly ? 0 : 1);
          await expect(header.getByRole('button', { name: 'Provision access' })).toHaveCount(variant.readOnly ? 0 : 1);
          await expect(header.getByRole('button', { name: 'Link existing' })).toHaveCount(variant.readOnly ? 0 : 1);
        } else {
          await expect(page.getByLabel('Upload profile photo')).toHaveCount(1);
          await expect(page.getByLabel('Upload profile cover')).toHaveCount(1);
        }
        if (variant.label === 'custom') {
          await expect(header.locator('[data-profile-avatar] img')).toBeVisible();
          expect(await header.locator('[data-profile-cover]').evaluate((el) => getComputedStyle(el).backgroundImage)).toContain('data:image');
        }
        if (variant.label === 'tenant' && path === '/profile') expect(await header.locator('[data-profile-cover]').evaluate((el) => getComputedStyle(el).backgroundImage)).toContain('data:image');
        if ((variant.label === 'default' && [320, 1440].includes(width)) || (variant.label === 'long' && width === 390)) {
          await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
          await header.screenshot({ path: `../../docs/profile-header-evidence/after-${path === '/profile' ? 'self' : 'employee'}-${width}-${variant.label}.png` });
        }
      }
      const results = await new AxeBuilder({ page }).include('.profile-header').analyze();
      expect(results.violations).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}
for (const scale of [1.25, 1.5, 2]) {
  for (const path of ['/employees/synthetic-person', '/profile']) {
    test(`${path} reflows at ${scale * 100}% desktop zoom equivalent`, async ({ page }) => {
      // Browser zoom reduces CSS viewport width. DPR alone does not test reflow.
      await page.setViewportSize({ width: Math.floor(1280 / scale), height: Math.floor(1000 / scale) });
      await mockProfile(page, variants[1].data);
      await page.goto(path);
      await verify(page);
    });
  }
}
test('profile actions, tab keyboard navigation and self-service links retain behavior', async ({ page }) => {
  await mockProfile(page);
  await page.goto('/employees/synthetic-person');
  const header = await verify(page);
  for (const name of ['Edit employee', 'Provision access', 'Link existing']) {
    await header.getByRole('button', { name }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
  }
  await header.getByRole('tab', { name: 'Personal', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(header.getByRole('tab', { name: 'Job', exact: true })).toBeFocused();
  await expect(page).toHaveURL(/tab=job/);
  for (const name of ['Time off', 'Attendance', 'Payroll']) {
    await header.getByRole('tab', { name: new RegExp(name) }).click();
    await expect(header.getByRole('tab', { name: new RegExp(name) })).toHaveAttribute('aria-selected', 'true');
  }
  await page.goto('/profile');
  await page.getByRole('link', { name: 'View public profile' }).click();
  await expect(page).toHaveURL(/employees\/synthetic-person/);
});
test('homepage personalization uses the same profile routes and long identity remains contained', async ({ page }) => {
  await mockProfile(page, variants[1].data, false, coverImage);
  await page.goto('/employee-home');
  for (const width of widths) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.getByRole('button', { name: 'Complete profile' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
  await page.getByRole('button', { name: 'Complete profile' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByLabel('Profile cover URL')).toBeVisible();
});
