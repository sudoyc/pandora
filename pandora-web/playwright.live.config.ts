import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

const systemBrowser = [
  '/usr/bin/chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
].find(existsSync);

const daemonUrl = new URL(
  process.env.PANDORA_LIVE_DAEMON_URL ?? 'http://127.0.0.1:7860',
).origin;

export default defineConfig({
  testDir: './tests/live',
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium-live',
      use: {
        ...devices['Desktop Chrome'],
        browserName: 'chromium',
        launchOptions: systemBrowser
          ? { executablePath: systemBrowser }
          : { channel: 'chrome' },
      },
    },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
    env: { VITE_PANDORA_DAEMON_URL: daemonUrl },
  },
});
