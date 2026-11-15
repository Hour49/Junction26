// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const css = readFileSync(new URL('./agent.css', import.meta.url), 'utf8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
);

it("AC-36 the plan pane's sticky rules are its own classes, not the edit card's figure (.ag-plan)", () => {
  // .ag-plan is EditCard's "Proposed plan" figure; a second .ag-plan rule made it sticky and window-tall on phones,
  // over the Accept button (e2e AC-32 phone).
  expect(css.match(/^\.ag-plan\s*\{/gm)).toHaveLength(1);
  expect(css).toMatch(/^\.ag-pane\s*\{[^}]*position:\s*sticky/m);
});

it('AC-38 scrolling the plan in the sheet never scrolls the chat behind it', () => {
  expect(css).toMatch(/^\.ag-sheet \.ag-pane-view\s*\{[^}]*overscroll-behavior:\s*contain/m);
});

it('R4-E13 a phone held sideways (height under 500 px) drops the ask bar chip row and the count', () => {
  const short = css.match(/@media \(max-height: 500px\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? '';
  expect(short).toMatch(/\.ag-bar \.ag-selrow,\s*\.ag-bar \.en-meta\s*\{\s*display:\s*none/);
});

it('R4-E11 a source number [n] is a 24 x 24 px hit area at least, by padding not a bigger glyph', () => {
  const cite = css.match(/^\.ag-cite\s*\{([^}]*)\}/m)?.[1] ?? '';
  expect(cite).toMatch(/min-width:\s*24px/);
  expect(cite).toMatch(/min-height:\s*24px/);
  expect(cite).toMatch(/font-size:\s*0\.8em/);
});
