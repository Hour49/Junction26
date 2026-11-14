// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const css = readFileSync(new URL('./engineer.css', import.meta.url), 'utf8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
);

it('EN-63 engineer.css has no colour literal: every colour is a --v-* token', () => {
  // var() fallbacks may carry a literal; nothing else may.
  const outside = css.replace(/var\([^()]*\)/g, '');
  expect(outside.match(/#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/gi)).toBeNull();
  expect(css).toMatch(/var\(--v-/);
});

it('EN-64 reduced motion turns off the press scale and the overlay animation', () => {
  const at = css.indexOf('@media (prefers-reduced-motion: reduce)');
  expect(at).toBeGreaterThan(-1);
  const block = css.slice(at);
  expect(block).toMatch(/\.en-overlay\s*\{[^}]*animation:\s*none/);
  expect(block).toMatch(/\.v-press:active\s*\{[^}]*transform:\s*none/);
});
