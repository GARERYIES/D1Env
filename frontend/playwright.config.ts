import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: { timeout: 10000 },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.D1ENV_E2E_URL ?? 'http://127.0.0.1:8765',
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1440, height: 1040 },
    // A bootstrap credential must never be captured in a trace or screenshot.
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
});
