import { defineConfig } from '@playwright/test';

// E2E_API_URL: a backend already running (real services, by hand); else the no-keys one started below.
const backend = process.env.E2E_API_URL ?? `http://127.0.0.1:${process.env.E2E_API_PORT ?? '8010'}`;
const preview = 'http://127.0.0.1:4173'; // vite.config.ts preview.port; 127.0.0.1, not localhost (::1 first)

const servers = [
  {
    command: 'npx vite preview --host 127.0.0.1',
    url: preview,
    env: { BACKEND_URL: backend },
    reuseExistingServer: false,
    timeout: 60_000,
  },
];
if (!process.env.E2E_API_URL) {
  servers.unshift({
    command: 'bash e2e/start-backend.sh',
    url: `${backend}/health`,
    env: { BACKEND_URL: backend },
    reuseExistingServer: false, // a developer's dev backend may have keys
    timeout: 120_000,
  });
}

export default defineConfig({
  testDir: 'e2e',
  // One backend for both projects, and the sample's fresh=true resets the last run's edits: never overlap.
  workers: 1,
  fullyParallel: false,
  retries: 0, // the path is deterministic; a flake is a bug
  timeout: 90_000,
  expect: { timeout: 10_000 },
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'list' : [['list'], ['html', { open: 'never' }]],
  use: { baseURL: preview, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    {
      name: 'phone',
      use: {
        browserName: 'chromium',
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: servers,
});
