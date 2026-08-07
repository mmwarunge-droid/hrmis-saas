import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

for (const path of [
  '/dashboard',
  '/profile',
  '/goals',
  '/documents',
]) {
  test(
    `${path} has no serious or critical accessibility violations`,
    async ({ page }) => {
      await page.goto(path);

      await expect(page).toHaveURL(
        new RegExp(`${path}/?$`),
      );
      await expect(page.locator('main')).toBeVisible();

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();

      const blocking = results.violations.filter(
        (item) =>
          ['serious', 'critical'].includes(item.impact),
      );

      expect(blocking).toEqual([]);
    },
  );
}
