// @vitest-environment node
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { expect, test } from 'vitest';

// CI's node job runs `npm test` but has no uv, so this check needs the committed OpenAPI file.
const openapi = new URL('../../../docs/api/openapi-v1.json', import.meta.url);
const missing = !existsSync(openapi);
if (missing) process.stderr.write('skip: docs/api/openapi-v1.json not found (npm run api:check)\n');

test.skipIf(missing)('src/api/schema.d.ts matches docs/api/openapi-v1.json', () => {
  const script = new URL('../../scripts/api-schema.mjs', import.meta.url);
  expect(() => execFileSync('node', [script.pathname, '--check'], { stdio: 'pipe' })).not.toThrow();
});
