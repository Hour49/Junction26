// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

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
  const phone = css.slice(css.indexOf('@media (max-width: 600px)'));
  expect(rulesFor('.project-picker', phone)).toMatch(/width:\s*100%/);
});

it('R1-5-4 long unbreakable file strings wrap inside main instead of widening the page', () => {
  // A project or file name with no break point (60 chars) set the ingest header's min-content width.
  const main = rulesFor('main', css);
  expect(main).toMatch(/min-width:\s*0/);
  expect(main).toMatch(/overflow-wrap:\s*anywhere/);
});
