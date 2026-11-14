// @vitest-environment node
import { Linter } from 'eslint';
import tseslint from 'typescript-eslint';
import { expect, it } from 'vitest';

interface Block {
  files?: string[];
  rules?: Record<string, unknown>;
}
// The config is plain JS with no types; loaded by URL so tsc does not ask for its declarations.
const configUrl = new URL('../../eslint.config.js', import.meta.url).href;
const { default: config, NO_HTML } = (await import(/* @vite-ignore */ configUrl)) as {
  default: Block[];
  NO_HTML: Linter.RuleEntry[];
};

const BAD = `
export const A = (p: { s: string }) => <div dangerouslySetInnerHTML={{ __html: p.s }} />;
export function b(el: HTMLElement, s: string) { el.innerHTML = s; }
`;
const GOOD = `export const A = (p: { s: string }) => <div>{p.s}</div>;`;

function lint(code: string) {
  return new Linter().verify(
    code,
    [
      {
        files: ['**/*.tsx'],
        languageOptions: {
          parser: tseslint.parser,
          parserOptions: { ecmaFeatures: { jsx: true } },
        },
        rules: { 'no-restricted-syntax': ['error', ...NO_HTML] as Linter.RuleEntry },
      },
    ],
    'src/x.tsx',
  );
}

it('SH-41 eslint refuses dangerouslySetInnerHTML and .innerHTML in src/', () => {
  const applies = config.some(
    (block) =>
      block.files?.includes('src/**/*.{ts,tsx}') &&
      JSON.stringify(block.rules?.['no-restricted-syntax']) ===
        JSON.stringify(['error', ...NO_HTML]),
  );
  expect(applies).toBe(true);
  expect(lint(BAD).map((m) => m.line)).toEqual([2, 3]);
  expect(lint(GOOD)).toEqual([]);
});
