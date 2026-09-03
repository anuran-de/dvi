import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
  resolve: { alias: { '@': resolve(__dirname, '.') } },
});
