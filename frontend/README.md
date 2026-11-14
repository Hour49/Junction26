# Frontend

Vite + React + TypeScript. Node 24 (`.nvmrc`), npm with the committed `package-lock.json`.

## Install and run

```bash
cd frontend && npm ci
npm run dev        # http://127.0.0.1:5173, proxies /api and /health to BACKEND_URL
```

Start the backend first (`backend/README.md`): it listens on `http://127.0.0.1:8000`, the default `BACKEND_URL`.
The app calls relative `/api` URLs; only the dev and preview proxies know where the backend is.

## Build and serve

```bash
cd frontend && npm ci && npm run build && npm run preview
```

Serves the frozen build at http://127.0.0.1:4173 and proxies `/api` and `/health` to `BACKEND_URL` (default
`http://127.0.0.1:8000`; e.g. `BACKEND_URL=http://127.0.0.1:9000 npm run preview`). No backend address is baked
into the bundle. Ports are fixed (dev 5173, preview 4173, `strictPort`): a busy port is an error, not another port.

## Check

```bash
./check.sh         # lint + prettier, tsc, vitest, vite build, API types fresh, npm audit
./check.sh quick   # lint + prettier, tsc: before a commit
npm run e2e        # Playwright, chromium at 390x844 and 1440x900, against `npm run preview`
```

First e2e run on a machine: `npx playwright install chromium` (CI: `--with-deps`). CI's generic node job runs
`npm ci`, `tsc --noEmit`, `npm run lint`, `npm test`, `npm run build` and `npm audit`.

Tests can import the backend's contract fixtures: `import project from '@fixtures/project.json'` reads
`../backend/tests/fixtures/api_v1/`.

## API types

`src/api/schema.d.ts` is generated from the backend OpenAPI; commit it with the change that caused it.

```bash
npm run api:gen    # from ../docs/api/openapi-v1.json, or dumped from ../backend with uv when that file is missing
npm run api:check  # fails with a diff when the committed file is stale (also a vitest test when the json exists)
```
