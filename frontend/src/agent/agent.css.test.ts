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
