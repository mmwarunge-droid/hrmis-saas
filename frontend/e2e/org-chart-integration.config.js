import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './integration',
  testMatch: 'org-chart-integration.spec.js',
  workers: 1,
  timeout: 120000,
  expect: { timeout: 10000 },
  use: {
    baseURL: 'http://localhost:5189',
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  outputDir: '/tmp/hrmis-org-integration/browser-results',
  reporter: 'list',
});
