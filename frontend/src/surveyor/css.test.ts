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
});
