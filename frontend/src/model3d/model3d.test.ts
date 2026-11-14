import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import { trace } from '../api/fixtures';
import { failure, model3dOf } from './model3d';

describe('model3d', () => {
  it('M3-1 model3dOf reads model_3d, null when missing', () => {
    expect(model3dOf(trace.file)).toBeNull();
    const m = { state: 'ready', reason: '', elements: 12 } as const;
    expect(model3dOf({ ...trace.file, model_3d: m })).toEqual(m);
  });

  it('M3-5/M3-6 failure words and whether to retry', () => {
    const tooBig = new ApiError(422, 'too_big', 'The model is too big for a 3D view (85 MB).');
    expect(failure(tooBig)).toEqual({ reason: tooBig.detail, retry: false });
    expect(failure(new ApiError(404, 'not-found', 'no such file'))).toEqual({
      reason: 'no 3D model for this file',
      retry: false,
    });
    expect(failure(new ApiError(500, 'internal', 'boom'))).toEqual({
      reason: 'boom (internal)',
      retry: true,
    });
    expect(failure(new Error('this browser cannot draw 3D'))).toEqual({
      reason: 'this browser cannot draw 3D',
      retry: true,
    });
  });

  it('M3-18 only scene.ts imports three, and scene only dynamically', () => {
    const files = (dir: string): string[] =>
      readdirSync(dir).flatMap((n) => {
        const p = join(dir, n);
        return statSync(p).isDirectory() ? files(p) : /\.tsx?$/.test(n) ? [p] : [];
      });
    const tests = /\.test\.tsx?$/;
    for (const f of files('src')) {
      const text = readFileSync(f, 'utf8');
      if (!f.endsWith(join('model3d', 'scene.ts')) && !tests.test(f))
        expect(text, f).not.toMatch(/from ['"]three(\/|['"])/);
      // a type-only import is erased by the build
      if (!tests.test(f))
        expect(text, f).not.toMatch(/^import (?!type )[^;]*from ['"]\.\/scene['"]/m);
    }
    expect(readFileSync('src/model3d/ModelView.tsx', 'utf8')).toContain("import('./scene')");
  });

  it('M3-20 model3d.css has no colour literal', () => {
    const css = readFileSync('src/model3d/model3d.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });
});

describe('role tokens', () => {
  it('M3-16 shell.css defines four different --v-3d-* role colours', () => {
    const css = readFileSync('src/shell/shell.css', 'utf8');
    const values = ['moved', 'removed', 'added', 'affected'].map(
      (r) => new RegExp(`--v-3d-${r}:\\s*([^;]+);`).exec(css)?.[1],
    );
    expect(values.every(Boolean)).toBe(true);
    expect(new Set(values).size).toBe(4);
  });
});
