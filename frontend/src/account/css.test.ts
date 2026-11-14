// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const css = readFileSync(new URL('./account.css', import.meta.url), 'utf8').replace(
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

it('AC-31 "Open workspace" is a soft accent pill', () => {
  const open = rulesFor('a.account-open', css);
  expect(open).toMatch(/background:\s*var\(--v-accent-soft\)/);
  expect(open).toMatch(/color:\s*var\(--v-accent-strong\)/);
  expect(open).toMatch(/border-radius:\s*980px/);
});

it('AC-31 at 720 px and below the fifth stat spans both columns', () => {
  const phone = css.slice(css.indexOf('@media (max-width: 720px)'));
  expect(rulesFor('.account-stats > div:nth-child(5)', phone)).toMatch(/grid-column:\s*1 \/ -1/);
});
