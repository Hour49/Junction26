// Pre-QA c (2026-11-14): conflicts card layout rules jsdom cannot see, checked on the CSS text.
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const css = readFileSync('src/surveyor/conflicts.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, ''); // vitest runs in frontend/

/** The declarations of rules naming `selector` exactly, inside `scope` (a media query's text) or the whole file. */
function rulesFor(selector: string, scope = css): string {
  const out: string[] = [];
  for (const m of scope.matchAll(/([^{}@]+)\{([^{}]*)\}/g)) {
    if (
      (m[1] ?? '')
        .split(',')
        .map((x) => x.trim())
        .includes(selector)
    )
      out.push(m[2] ?? '');
  }
  return out.join(';');
}

function media(query: string): string {
  const at = css.indexOf(`@media ${query}`);
  expect(at, `@media ${query}`).toBeGreaterThanOrEqual(0);
  let depth = 0;
  for (let i = css.indexOf('{', at); i < css.length; i++) {
    if (css[i] === '{') depth++;
    if (css[i] === '}' && --depth === 0) return css.slice(at, i);
  }
  return css.slice(at);
}

it('CF-26 on a phone the pill sits above the card title, which gets the full width', () => {
  const phone = media('(max-width: 600px)');
  expect(rulesFor('.cf-card-top', phone)).toMatch(/flex-direction:\s*column-reverse/);
  expect(rulesFor('.cf-card-top', phone)).toMatch(/align-items:\s*flex-start/);
});

it('CF-27 the button row stays right-aligned whatever the action line says (also when it wraps)', () => {
  expect(rulesFor('.cf-buttons')).toMatch(/margin-left:\s*auto/);
  expect(rulesFor('.cf-buttons')).toMatch(/justify-content:\s*flex-end/);
});
