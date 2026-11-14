import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './profile-header',
  workers: 1,
  timeout: 90000,
  use: { baseURL: process.env.E2E_BASE_URL || 'http://localhost:5193', trace: 'off' },
  outputDir: '/tmp/hrmis-profile-header-results',
  reporter: 'list',
});
