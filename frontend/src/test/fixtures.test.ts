// @vitest-environment node
import { expect, test } from 'vitest';
import type { components } from '../api/schema';

// Empty when the backend fixtures folder is missing (a checkout without backend/).
const files = import.meta.glob<{ default: unknown }>('@fixtures/*.json', { eager: true });
const project = Object.entries(files).find(([path]) => path.endsWith('/project.json'))?.[1];
// stderr, because vitest drops console output of a file whose tests all skip.
if (!project)
  process.stderr.write('skip: ../backend/tests/fixtures/api_v1/project.json not found\n');

test.skipIf(!project)('backend api_v1 fixtures import as JSON', () => {
  const body = project?.default as components['schemas']['ProjectView'];
  expect(body.id).toMatch(/^[0-9a-f]{12}$/);
});
