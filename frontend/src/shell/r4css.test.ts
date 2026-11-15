// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

it('R4-E5 the "Also as" links are at least 24 px high', () => {
  const css = readFileSync(new URL('../engineer/engineer.css', import.meta.url), 'utf8');
  expect(css).toMatch(/\.en-also a\s*\{[^}]*min-height:\s*24px/);
});

/** WCAG contrast of two #rrggbb colours. */
function ratio(a: string, b: string): number {
  const lum = (h: string) => {
    const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
    const [r, g, bl] = c.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
    return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (bl ?? 0);
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

it('R4-E12 --v-muted is at least 4.5:1 on every tinted background token', () => {
  const css = readFileSync(new URL('./shell.css', import.meta.url), 'utf8');
  const token = (n: string) => new RegExp(`--${n}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1] ?? '';
  const muted = token('v-muted');
  expect(muted).not.toBe('');
  for (const n of [
    'v-bg',
    'v-surface',
    'v-fill',
    'v-accent-soft',
    'v-ok-soft',
    'v-seg',
    'v-grey',
    'v-warn-soft',
    'v-danger-soft',
  ])
    expect(ratio(muted, token(n)), n).toBeGreaterThanOrEqual(4.5);
});
