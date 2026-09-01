import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  webServer: {
    command: 'npx serve out -l 4321',
    url: 'http://localhost:4321',
    timeout: 60000,
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: 'http://localhost:4321' },
});
