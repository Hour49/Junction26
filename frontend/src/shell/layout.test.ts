// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { PRODUCT_NAME } from './strings';

const css = readFileSync(new URL('./shell.css', import.meta.url), 'utf8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
);

/** The declarations of every rule whose selector list names `selector` exactly, joined. */
function rulesFor(selector: string, source: string): string {
  const out: string[] = [];
  for (const match of source.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selectors = (match[1] ?? '').split(',').map((s) => s.trim());
    if (selectors.includes(selector)) out.push(match[2] ?? '');
  }
  return out.join(';');
}

it('R1-5-4 the header project picker is constrained to the header width (jsdom has no layout)', () => {
  // A native <select> is as wide as its longest option unless min-width and max-width stop it.
  const all = rulesFor('.project-picker', css);
  expect(all).toMatch(/min-width:\s*0/);
  expect(all).toMatch(/max-width:\s*100%/);
  const phone = css.slice(css.indexOf('@media (max-width: 720px)'));
  expect(rulesFor('.project-picker', phone)).toMatch(/width:\s*100%/);
});

it('R1-5-4 long unbreakable file strings wrap inside main instead of widening the page', () => {
  // A project or file name with no break point (60 chars) set the ingest header's min-content width.
  const main = rulesFor('main', css);
  expect(main).toMatch(/min-width:\s*0/);
  expect(main).toMatch(/overflow-wrap:\s*anywhere/);
});

const TOKENS: Record<string, string> = {
  '--v-bg': '#f5f5f7',
  '--v-surface': '#ffffff',
  '--v-text': '#1d1d1f',
  '--v-muted': '#6e6e73',
  '--v-line': '#d2d2d7',
  '--v-accent': '#3d5a4f',
  '--v-accent-strong': '#2a3f37',
  '--v-warn': '#8a4b00',
  '--v-warn-soft': '#fff3e0',
  '--v-ok': '#1f6b3b',
  '--v-danger': '#a1302a',
  '--v-radius': '24px',
  '--v-shadow': '0 1px 2px rgba(0, 0, 0, 0.04), 0 12px 32px rgba(0, 0, 0, 0.06)',
  '--v-font': '-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif',
  '--v-text-2': '#48484a',
  '--v-ok-soft': '#e8f5ec',
  '--v-danger-soft': '#fdecea',
  '--v-accent-soft': '#e6eeea',
  '--v-fill': '#f0f1f0',
};

/** Values compared with spaces normalised and quotes unified (prettier rewrites both). */
const same = (value: string) => value.replace(/\s+/g, ' ').replace(/'/g, '"').trim();

function declarations(block: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const part of block.split(';')) {
    const colon = part.indexOf(':');
    if (colon > 0) out.set(part.slice(0, colon).trim(), same(part.slice(colon + 1)));
  }
  return out;
}

it('SH-51 :root defines the twenty Vellum tokens with their values', () => {
  const root = declarations(rulesFor(':root', css));
  for (const [name, value] of Object.entries(TOKENS))
    expect(root.get(name), name).toBe(same(value));
});

it('SH-52 no colour is hard-coded in src/shell CSS outside :root, bar the three allowed', () => {
  const rest = css
    .replace(/:root\s*\{[^{}]*\}/, '')
    .replace(/rgba\(255, 255, 255, 0\.72\)/g, '')
    .replace(/rgba\(0, 0, 0, 0\.06\)/g, '')
    .replace(/rgba\(0, 0, 0, 0\.12\)/g, '');
  expect(rest).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
});

it("SH-57 the base classes carry the designs' values", () => {
  const card = rulesFor('.v-card', css);
  expect(card).toMatch(/border-radius:\s*var\(--v-radius\)/);
  expect(card).toMatch(/box-shadow:\s*var\(--v-shadow\)/);
  const btn = rulesFor('.v-btn', css);
  expect(btn).toMatch(/background:\s*var\(--v-accent\)/);
  expect(btn).toMatch(/border-radius:\s*980px/);
  expect(btn).toMatch(/min-height:\s*44px/);
  expect(rulesFor('.v-btn--secondary', css)).toMatch(/background:\s*var\(--v-fill\)/);
  expect(rulesFor('.v-pill', css)).toMatch(/border-radius:\s*980px/);
  for (const [tone, text, fill] of [
    ['ok', 'ok', 'ok-soft'],
    ['warn', 'warn', 'warn-soft'],
    ['danger', 'danger', 'danger-soft'],
    ['accent', 'accent-strong', 'accent-soft'],
  ] as const) {
    const rule = rulesFor(`.v-pill--${tone}`, css);
    expect(rule).toMatch(new RegExp(`color:\\s*var\\(--v-${text}\\)`));
    expect(rule).toMatch(new RegExp(`background:\\s*var\\(--v-${fill}\\)`));
  }
  expect(rulesFor('.v-segmented', css)).toMatch(/background:\s*var\(--v-fill\)/);
  for (const [page, width] of [
    ['.v-page', '1120px'],
    ['.v-page--narrow', '820px'],
    ['.v-page--mid', '1040px'],
    ['.v-page--wide', '1280px'],
  ] as const)
    expect(rulesFor(page, css)).toMatch(new RegExp(`max-width:\\s*${width}`));
  expect(rulesFor('.v-title', css)).toMatch(/font-size:\s*44px/);
  expect(rulesFor('.v-hero', css)).toMatch(/font-size:\s*64px/);
});

it('SH-58 focus ring on every focusable element, no outline: none, reduced motion', () => {
  const focusable = ['a', 'button', 'select', 'input', 'textarea', 'summary', '[tabindex]'];
  for (const el of focusable) {
    const ring = rulesFor(`${el}:focus-visible`, css);
    expect(ring, el).toMatch(/outline:\s*2px solid var\(--v-accent\)/);
    expect(ring, el).toMatch(/outline-offset:\s*2px/);
  }
  // The one exception: App focuses <main tabindex=-1> on a route change; it is not a control (pre-QA 12:00).
  const quiet = "main[tabindex='-1']";
  expect(rulesFor(`${quiet}:focus-visible`, css)).toMatch(/outline:\s*none/);
  expect(rulesFor(`${quiet}:focus`, css)).toMatch(/outline:\s*none/);
  const others = css.replace(
    /main\[tabindex='-1'\]:focus,\s*main\[tabindex='-1'\]:focus-visible\s*\{[^}]*\}/,
    '',
  );
  expect(others).not.toMatch(/outline:\s*(none|0)\b/);
  const motion = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'));
  expect(css).toContain('@media (prefers-reduced-motion: reduce)');
  expect(rulesFor('*', motion)).toMatch(/transition:\s*none !important/);
  expect(rulesFor('*', motion)).toMatch(/animation:\s*none !important/);
});

it('SH-59 body uses the tokens and no font or stylesheet comes from another origin', () => {
  const body = rulesFor('body', css);
  expect(body).toMatch(/background:\s*var\(--v-bg\)/);
  expect(body).toMatch(/color:\s*var\(--v-text\)/);
  expect(body).toMatch(/font:\s*16px\/1\.5 var\(--v-font\)/);
  const src = new URL('../', import.meta.url);
  const sheets = readdirSync(src, { recursive: true, encoding: 'utf8' }).filter((f) =>
    f.endsWith('.css'),
  );
  expect(sheets.length).toBeGreaterThan(1);
  for (const f of sheets) expect(readFileSync(new URL(f, src), 'utf8'), f).not.toMatch(/https?:/);
  expect(readFileSync(new URL('../../index.html', import.meta.url), 'utf8')).not.toMatch(/https?:/);
});

it('SH-62 the sticky header is opaque, above page content, and its height is --v-header-h', () => {
  const header = rulesFor('.app-header', css.slice(0, css.indexOf('@media')));
  expect(header).toMatch(/position:\s*sticky/);
  expect(header).toMatch(/top:\s*0/);
  expect(header).toMatch(/background:\s*var\(--v-surface\)/);
  expect(header).not.toMatch(/background:[^;]*rgba|backdrop-filter/);
  // Screens' own layers go up to 5 (engineer.css); the header stays above them.
  expect(Number(/z-index:\s*(\d+)/.exec(header)?.[1])).toBeGreaterThanOrEqual(10);
  // 76 px = row padding 14 + 14 and the 48 px pills.
  const desktop = css.slice(0, css.indexOf('@media'));
  expect(declarations(rulesFor(':root', desktop)).get('--v-header-h')).toBe('76px');
  expect(rulesFor('.app-header-row', css)).toMatch(/padding:\s*14px 24px/);
  expect(rulesFor('.header-pill', css)).toMatch(/min-height:\s*48px/);
  // Phone: three rows would cover a quarter of the screen, so the header scrolls away and covers nothing.
  const phone = css.slice(css.indexOf('@media (max-width: 720px)'));
  expect(rulesFor('.app-header', phone)).toMatch(/position:\s*static/);
  expect(declarations(rulesFor(':root', phone)).get('--v-header-h')).toBe('0px');
});

it('SH-63 the browser tab title is the product name', () => {
  const html = readFileSync(new URL('../../index.html', import.meta.url), 'utf8');
  expect(/<title>([^<]*)<\/title>/.exec(html)?.[1]).toBe(PRODUCT_NAME);
});
