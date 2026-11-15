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

/** The declarations of every rule whose selector list names `selector` exactly, joined. */
function rulesFor(selector: string): string {
  const out: string[] = [];
  for (const match of css.matchAll(/([^{}@]+)\{([^{}]*)\}/g)) {
    const selectors = (match[1] ?? '').split(',').map((s) => s.trim());
    if (selectors.includes(selector)) out.push(match[2] ?? '');
  }
  return out.join(';');
}

it('EN-71 the ask box is a solid band: nothing on the page shows through it (golden 06/07)', () => {
  expect(rulesFor('.en-ask')).toMatch(/background:\s*var\(--v-bg\)/);
  // EN-81 amends: only the band must be solid; the pill on top of it may be translucent
  expect(rulesFor('.en-ask')).not.toMatch(/transparent|backdrop-filter/);
});

it('EN-71 a turn scrolled into view stops below the sticky site header', () => {
  expect(rulesFor('.en-turn')).toMatch(
    /scroll-margin-top:\s*calc\(var\(--v-header-h[^)]*\)\s*\+\s*\d+px\)/,
  );
});

it('EN-79 the ask bar focus ring follows the pill, not a square box around the input (QA R4b-3)', () => {
  expect(rulesFor('.en-askpill input:focus-visible')).toMatch(/outline:\s*none/);
  const ring = rulesFor('.en-askpill:has(input:focus-visible)');
  expect(ring).toMatch(/outline:\s*2px solid var\(--v-accent\)/);
  expect(ring).toMatch(/outline-offset:\s*2px/);
  expect(rulesFor('.en-askpill')).toMatch(/border-radius:\s*980px/);
});

it('EN-80 the place row and the file name share the row without covering each other (QA R5-c-2)', () => {
  expect(rulesFor('.en-plan:has(> .en-place) .vw-name')).toMatch(/max-width:\s*50%/);
  expect(rulesFor('.en-place')).toMatch(/max-width:\s*calc\(50% - 32px\)/);
});

it('CH-37 W2: one column at every width, the drawing card under its image (no half-empty side column)', () => {
  expect(rulesFor('.en-chatcard')).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\);/);
  expect(rulesFor('.en-chatcard')).not.toMatch(/260px/);
});

it('CH-38 the chat column is the demo 820 px (868 px with the 24 px gutters)', () => {
  expect(rulesFor('.en-chat')).toMatch(/max-width:\s*868px/);
});

it('EN-81 the ask bar takes the demo look: translucent pill on the solid band, a filled send button', () => {
  const pill = rulesFor('.en-askpill');
  expect(pill).toMatch(/background:\s*color-mix\(in srgb, var\(--v-surface\) 86%, transparent\)/);
  expect(pill).toMatch(/backdrop-filter:\s*blur\(20px\) saturate\(180%\)/);
  expect(pill).toMatch(/padding:\s*6px 6px 6px 20px/);
  expect(rulesFor('.en-send:disabled')).not.toMatch(/opacity:\s*0/);
  expect(rulesFor('.en-ask')).toMatch(/background:\s*var\(--v-bg\)/);
});

it('EN-81 the arrows on plans and references: 92% surface, the demo shadow', () => {
  const nav = rulesFor('.en-nav');
  expect(nav).toMatch(/background:\s*color-mix\(in srgb, var\(--v-surface\) 92%, transparent\)/);
  expect(nav).toMatch(
    /box-shadow:\s*0 2px 10px color-mix\(in srgb, var\(--v-text\) 18%, transparent\)/,
  );
});

it('CH-39 ui-bugs 8: no Show it on link style left; the why line smaller', () => {
  expect(css).not.toMatch(/\.en-show\b/);
  expect(rulesFor('.en-lead--why')).toMatch(/font-size:\s*14px/);
});

it('deep QA research-lead 1: a text answer keeps its line breaks at reading size', () => {
  expect(rulesFor('.en-value--text')).toMatch(/white-space:\s*pre-line/);
  expect(rulesFor('.en-value--text')).toMatch(/font-size:\s*15px/);
});
