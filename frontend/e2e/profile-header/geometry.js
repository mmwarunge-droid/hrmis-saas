import { expect } from '@playwright/test';

export async function verify(page) {
  const header = page.locator('.profile-header');
  await expect(header.locator('h1')).toBeVisible();
  // Wait for the shell's entrance animation, not a guessed viewport offset.
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length)).toBe(0);
  const boxes = await header.evaluate((el) => {
    const box = (selector) => {
      const r = el.querySelector(selector)?.getBoundingClientRect();
      return r && { top: r.top, bottom: r.bottom, left: r.left, right: r.right };
    };
    return { cover: box('[data-profile-cover]'), identity: box('[data-profile-identity]'), name: box('h1'), avatar: box('[data-profile-avatar]'), actions: box('[data-profile-actions]'), tabs: box('[data-profile-tabs]'), body: box('[data-profile-body]') };
  });
  for (const key of ['identity', 'name', 'actions']) expect(boxes[key].top).toBeGreaterThanOrEqual(boxes.cover.bottom - 1);
  expect(boxes.avatar.top).toBeLessThan(boxes.cover.bottom);
  expect(boxes.avatar.bottom).toBeGreaterThan(boxes.cover.bottom);
  // Identity and actions must not collide with each other or the avatar.
  const disjoint = (a, b) => a.bottom <= b.top + 1 || b.bottom <= a.top + 1 || a.right <= b.left + 1 || b.right <= a.left + 1;
  expect(disjoint(boxes.identity, boxes.avatar)).toBe(true);
  expect(disjoint(boxes.identity, boxes.actions)).toBe(true);
  if (boxes.tabs) expect(boxes.tabs.top).toBeGreaterThanOrEqual(boxes.body.bottom - 1);
  for (const control of await header.locator('[data-profile-identity] > div > *, [data-profile-actions] > *').all()) {
    const rect = await control.boundingBox();
    if (rect) expect(rect.y).toBeGreaterThanOrEqual(boxes.cover.bottom - 1);
  }
  expect(await header.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(255, 255, 255)');
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  return header;
}
