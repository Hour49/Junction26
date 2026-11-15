// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

// The screen is styled with Tailwind classes (shadcn migration): the rules live in the component source.
const tsx = readFileSync(new URL('./AccountScreen.tsx', import.meta.url), 'utf8');

it('AC-31 "Open workspace" is a soft accent pill', () => {
  const open = tsx.slice(tsx.lastIndexOf('<Button', tsx.indexOf('Open workspace')));
  expect(open).toMatch(/size="pill"/);
  expect(open).toMatch(/bg-accent text-accent-strong/);
});

it('AC-31 at 720 px and below the fifth stat spans both columns', () => {
  expect(tsx).toContain('max-[720px]:grid-cols-2');
  expect(tsx).toContain('max-[720px]:[&>div:nth-child(5)]:col-span-full');
});

it("SH-81 the account item focus ring is the shell's 3px", () => {
  // The item is a plain <button>: shell.css's `button:focus-visible` ring applies, and nothing here removes it.
  expect(tsx).not.toMatch(/outline-none|outline-hidden/);
});

it('qa-c R1 the stat values sit left (no browser dd indent) and never wrap ("0 of 196" on one line)', () => {
  const dd = /<dd className="([^"]*)"/.exec(tsx)?.[1] ?? '';
  expect(dd.split(' ')).toContain('m-0');
  expect(dd.split(' ')).toContain('whitespace-nowrap');
});
