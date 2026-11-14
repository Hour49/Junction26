import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Where /api and /health go; the bundle itself only uses relative URLs.
const backend = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
const proxy = { '/api': backend, '/health': backend };
// Backend contract fixtures (docs/API.md): tests read them, the app never does.
const fixtures = fileURLToPath(new URL('../backend/tests/fixtures/api_v1', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@fixtures': fixtures } },
  server: { port: 5173, strictPort: true, proxy, fs: { allow: ['.', fixtures] } },
  preview: { port: 4173, strictPort: true, proxy },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    // The on-disk transform cache keeps an import.meta.glob result after the globbed folder changes.
    fsModuleCache: false,
  },
});
