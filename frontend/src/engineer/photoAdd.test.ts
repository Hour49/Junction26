// The added photo's status line in the backend's own words (chat.md CH-18, CH-19).
import { expect, it } from 'vitest';
import type { FileStatus } from '../api';
import { fileReadAsPlan } from '../api/fixtures';
import { readLine } from './photoAdd';

const file = (state: FileStatus['state'], reason: string): FileStatus => ({
  ...fileReadAsPlan,
  state,
  reason,
});

it('CH-18 ready: read, can be asked, with what was read', () => {
  expect(readLine('a.jpg', file('ready', 'read on the image route: 4 elements, 1 room.'))).toBe(
    'a.jpg is read: you can ask about it (read on the image route: 4 elements, 1 room).',
  );
});

it('CH-19 flagged and read: the flag in the backend words, no promise of answers', () => {
  const why =
    'a phone photo, read without perspective correction (4 elements, 1 room, scale found)';
  expect(readLine('a.jpg', file('flagged', why))).toBe(`a.jpg is flagged: ${why}.`);
});

it('CH-19 flagged with nothing read: says not read, never "you can ask"', () => {
  const why = 'not read: this setup has no reader for the image route (0 elements, 0 rooms)';
  const line = readLine('a.jpg', file('flagged', `${why}.`));
  expect(line).toBe(`a.jpg is flagged: ${why}.`);
  expect(line).not.toMatch(/you can ask/);
});

it('CH-19 set aside, text only or gone: not read as a plan, with why', () => {
  expect(readLine('a.jpg', file('set_aside', 'not a plan: a cat.'))).toBe(
    'a.jpg was not read as a plan: not a plan: a cat.',
  );
  expect(readLine('a.jpg', file('text_only', 'a text document.'))).toBe(
    'a.jpg was not read as a plan: a text document.',
  );
  expect(readLine('a.jpg', undefined)).toBe(
    'a.jpg was not read as a plan: it is not in the project.',
  );
});
