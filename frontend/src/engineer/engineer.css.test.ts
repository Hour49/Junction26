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
  for (const sel of ['.en-ask', '.en-askpill']) {
    expect(rulesFor(sel)).not.toMatch(/transparent|backdrop-filter/);
  }
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

it('CH-37 the chat answer card: figure and side in two columns (1.4 : 1), one column at 900 px or less', () => {
  expect(rulesFor('.en-chatcard')).toMatch(
    /grid-template-columns:\s*minmax\(0,\s*1\.4fr\)\s*minmax\(0,\s*1fr\)/,
  );
  // the phone rule must come after the base rule, or the base wins (same specificity)
  const base = css.search(/\.en-chatcard\s*\{[^}]*1\.4fr/);
  const phone = css.slice(base);
  expect(phone).toMatch(
    /@media \(max-width: 900px\)[^@]*\.en-chatcard\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  );
});

it('CH-38 the chat column is the demo 820 px (868 px with the 24 px gutters)', () => {
  expect(rulesFor('.en-chat')).toMatch(/max-width:\s*868px/);
});
