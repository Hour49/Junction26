import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// read from disk: vitest hands `?raw` CSS imports over empty, so such a check passes on anything
const read = (name: string) => readFileSync(`src/surveyor/${name}`, 'utf8'); // vitest runs in frontend/
const surveyorCss = read('surveyor.css');
const conflictsCss = read('conflicts.css');

// SV-50: colours and fonts come from the --v-* tokens (shared.md); only the monospace stack is spelled out.
const literal = /#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/i;
const fonts = (css: string) =>
  [...css.matchAll(/font-family:\s*([^;]+);/g)].map((m) => (m[1] ?? '').trim());

describe('surveyor styles', () => {
  it.each([
    ['surveyor.css', surveyorCss],
    ['conflicts.css', conflictsCss],
  ])('SV-50 %s holds no colour literal and no other font', (_, css) => {
    expect(css.length).toBeGreaterThan(100);
    expect(css.split('\n').filter((l) => literal.test(l))).toEqual([]);
    for (const f of fonts(css))
      expect(['var(--v-font)', 'ui-monospace, Menlo, monospace']).toContain(f);
  });

  /** The declarations of the first rule whose selector is exactly `selector`. */
  const rule = (css: string, selector: string) => {
    const at = css.indexOf(`${selector} {`);
    expect(at, `rule ${selector}`).toBeGreaterThanOrEqual(0);
    return css.slice(at, css.indexOf('}', at));
  };

  it('R1-4-2 at desktop the takeoff column gets a share of the width, not a fixed 420 px', () => {
    const columns = /grid-template-columns:\s*([^;]+);/.exec(
      rule(surveyorCss, '.sv-screen.sv-work'),
    )?.[1];
    // side list, plan, takeoff: the takeoff is a flexible track at least as wide as the plan's
    expect(columns).toMatch(/^\d+px minmax\(0, 1fr\) minmax\(0, 1(\.\d+)?fr\)$/);
  });

  it('R1-4-2 the sticky takeoff panel stops under the site header (--v-header-h)', () => {
    const panel = rule(surveyorCss, '  .sv-work .sv-panel');
    expect(panel).toContain('top: var(--v-header-h, 0px);');
    expect(panel).toMatch(/max-height: calc\(100vh - var\(--v-header-h, 0px\)( - \d+px)?\);/);
  });
});
