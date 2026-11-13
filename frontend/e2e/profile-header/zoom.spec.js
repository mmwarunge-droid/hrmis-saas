import { chromium, expect, test } from '@playwright/test';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { mockProfile } from './fixtures.js';
import { verify } from './geometry.js';

for (const scale of [1.25, 1.5, 2]) {
  test(`native Chromium tab zoom ${scale * 100}% keeps both profile headers below their covers`, async () => {
    // A temporary local-only extension invokes native browser zoom, not CSS zoom,
    // pinch scaling or an artificial devicePixelRatio. Never shipped with the app.
    const root = mkdtempSync(join(tmpdir(), 'profile-zoom-'));
    const extension = join(root, 'extension');
    mkdirSync(extension);
    writeFileSync(join(extension, 'manifest.json'), JSON.stringify({ manifest_version: 3, name: 'Local profile zoom check', version: '1.0', permissions: ['tabs'], host_permissions: ['http://localhost:5193/*'], background: { service_worker: 'background.js' } }));
    writeFileSync(join(extension, 'background.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
    let context;
    try {
      context = await chromium.launchPersistentContext(join(root, 'browser'), {
        channel: 'chromium', headless: true, viewport: null,
        args: ['--window-size=1280,1000', `--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
      });
      const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
      const page = await context.newPage();
      await mockProfile(page, { full_name: 'Mary Example with a long family name for zoom testing', job_title: 'Senior People Operations and Organizational Development Specialist' });
      for (const path of ['/employees/synthetic-person', '/profile']) {
        await page.goto(`http://localhost:5193${path}`);
        await worker.evaluate(async () => {
          const [tab] = await chrome.tabs.query({ url: 'http://localhost:5193/*' });
          await chrome.tabs.setZoom(tab.id, 1);
        });
        await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBe(1);
        const normalWidth = await page.evaluate(() => innerWidth);
        const applied = await worker.evaluate(async (zoom) => {
          const [tab] = await chrome.tabs.query({ url: 'http://localhost:5193/*' });
          await chrome.tabs.setZoom(tab.id, zoom);
          return chrome.tabs.getZoom(tab.id);
        }, scale);
        expect(applied).toBe(scale);
        await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBe(scale);
        expect(Math.abs(await page.evaluate(() => innerWidth) - normalWidth / scale)).toBeLessThanOrEqual(2);
        await verify(page);
      }
    } finally {
      await context?.close();
      rmSync(root, { recursive: true, force: true });
    }
  });
}
