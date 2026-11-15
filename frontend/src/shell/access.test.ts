// @vitest-environment node
// QA round 2 angle D (R2-D2, R2-D5): contrast and tap size, read from the CSS the app ships.
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const shell = read('./shell.css');

/** The declarations of every rule whose selector list names `selector` exactly, joined. */
function rulesFor(selector: string, source: string): string {
  const out: string[] = [];
  for (const match of source.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selectors = (match[1] ?? '').split(',').map((s) => s.trim());
    if (selectors.includes(selector)) out.push(match[2] ?? '');
  }
  return out.join(';');
}
const prop = (decls: string, name: string) =>
  [...decls.matchAll(new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;]+)`, 'g'))].at(-1)?.[1]?.trim();
const token = (name: string) => must(shell.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`))?.[1]);
function must<T>(v: T | undefined | null): T {
  if (v == null) throw new Error('missing');
  return v;
}
/** A colour as the CSS writes it: #rrggbb, #fff, or var(--v-x[, fallback]) from shell.css. */
function hex(value: string): string {
  const v = value.match(/^var\(--([\w-]+)/)?.[1];
  const h = v ? token(v) : value;
  return h.replace(/^#(.)(.)(.)$/, '#$1$1$2$2$3$3');
}
function contrast(a: string, b: string): number {
  const lum = (h: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(h.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }) as [number, number, number];
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [x, y] = [lum(hex(a)), lum(hex(b))].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
}

it.each([
  ['../viewer/viewer.css', '.vw-hl-legend b'],
  ['../agent/multi/multi.css', '.ms-count'],
])('R2-D2 the numbers on the orange marks (%s %s) read at >= 4.5:1', (file, selector) => {
  const decls = rulesFor(selector, read(file));
  const ratio = contrast(must(prop(decls, 'color')), must(prop(decls, 'background')));
  expect(ratio).toBeGreaterThanOrEqual(4.5);
});

it('R2-D5 the header country pill is at least 44 px wide', () => {
  expect(prop(rulesFor('.country-button', shell), 'min-width')).toBe('44px');
});
