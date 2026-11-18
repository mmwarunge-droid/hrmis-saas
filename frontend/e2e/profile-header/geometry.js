import { expect } from '@playwright/test';

export async function verify(page, { layoutTimeout = 5000 } = {}) {
  const header = page.locator('.profile-header');
  await expect(header.locator('h1')).toBeVisible();
  // Fonts/images and smooth scrolling are not covered by getAnimations().
  // Read every rectangle in one frame; never compare different scroll offsets.
  const boxes = await header.evaluate(async (el, timeout) => {
    const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
    const read = () => {
      const rect = node => {
        const r = node?.getBoundingClientRect();
        return r && { top: r.top, bottom: r.bottom, left: r.left, right: r.right };
      };
      const box = selector => rect(el.querySelector(selector));
      return {
        cover: box('[data-profile-cover]'), identity: box('[data-profile-identity]'),
        name: box('h1'), avatar: box('[data-profile-avatar]'), actions: box('[data-profile-actions]'),
        tabs: box('[data-profile-tabs]'), body: box('[data-profile-body]'),
        controls: [...el.querySelectorAll('[data-profile-identity] > div > *, [data-profile-actions] > *')].map(rect),
        scrollX, scrollY,
      };
    };
    let previous;
    let stableFrames = 0;
    let stopped = false;
    let timer;
    const started = performance.now();
    const animations = () => document.getAnimations().filter(a => {
      const target = a.effect?.target;
      return a.playState === 'running' && target instanceof Element && (el.contains(target) || target.contains(el));
    });
    const settle = async () => {
      await document.fonts.ready;
      await Promise.all([...el.querySelectorAll('img')].map(img => img.decode().catch(() => {})));
      while (!stopped && stableFrames < 3) {
        await frame();
        const current = read();
        stableFrames = !animations().length && JSON.stringify(current) === JSON.stringify(previous) ? stableFrames + 1 : 0;
        previous = current;
      }
      return previous;
    };
    try {
      return await Promise.race([
        settle(),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error(`Profile layout did not settle: ${JSON.stringify({
            elapsedMs: Math.round(performance.now() - started), timeoutMs: timeout,
            url: location.pathname, viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
            stableFrames, fonts: document.fonts.status,
            images: [...el.querySelectorAll('img')].map(img => ({ complete: img.complete, naturalWidth: img.naturalWidth })),
            runningAnimations: animations().map(a => ({ currentTime: a.currentTime, playState: a.playState })),
            previous, current: read(),
          })}`)), timeout);
        }),
      ]);
    } finally {
      stopped = true;
      clearTimeout(timer);
    }
  }, layoutTimeout);
  for (const key of ['identity', 'name', 'actions']) expect(boxes[key].top).toBeGreaterThanOrEqual(boxes.cover.bottom - 1);
  expect(boxes.avatar.top).toBeLessThan(boxes.cover.bottom);
  expect(boxes.avatar.bottom).toBeGreaterThan(boxes.cover.bottom);
  // Identity and actions must not collide with each other or the avatar.
  const disjoint = (a, b) => a.bottom <= b.top + 1 || b.bottom <= a.top + 1 || a.right <= b.left + 1 || b.right <= a.left + 1;
  expect(disjoint(boxes.identity, boxes.avatar)).toBe(true);
  expect(disjoint(boxes.identity, boxes.actions)).toBe(true);
  if (boxes.tabs) expect(boxes.tabs.top).toBeGreaterThanOrEqual(boxes.body.bottom - 1);
  for (const rect of boxes.controls) {
    if (rect) expect(rect.top).toBeGreaterThanOrEqual(boxes.cover.bottom - 1);
  }
  expect(await header.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(255, 255, 255)');
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  return header;
}
