// The added photo's status line: short, with the backend's own words as the why on demand (chat.md CH-18, CH-19;
// qa-a r10 live-add-photo item 2).
import { expect, it } from 'vitest';
import type { FileStatus } from '../api';
import { fileReadAsPlan } from '../api/fixtures';
import { readLine } from './photoAdd';

const file = (state: FileStatus['state'], reason: string): FileStatus => ({
  ...fileReadAsPlan,
  state,
  reason,
});

it('CH-18 ready: a short line that it can be asked; what was read is the why', () => {
  expect(readLine('a.jpg', file('ready', 'read on the image route: 4 elements, 1 room.'))).toEqual({
    line: 'a.jpg is read: you can ask about it.',
    why: 'read on the image route: 4 elements, 1 room',
  });
});

it('CH-19 flagged and read: a short "flagged" line, the backend words as the why, no promise of answers', () => {
  const why =
    'a phone photo, read without perspective correction (4 elements, 1 room, scale found)';
  expect(readLine('a.jpg', file('flagged', why))).toEqual({ line: 'a.jpg is flagged.', why });
});

it('CH-19 flagged with nothing read: never "you can ask"', () => {
  const why = 'not read: this setup has no reader for the image route (0 elements, 0 rooms)';
  const read = readLine('a.jpg', file('flagged', `${why}.`));
  expect(read).toEqual({ line: 'a.jpg is flagged.', why });
  expect(read.line).not.toMatch(/you can ask/);
});

it('CH-19 set aside, text only or gone: not read as a plan, with why', () => {
  expect(readLine('a.jpg', file('set_aside', 'not a plan: a cat.'))).toEqual({
    line: 'a.jpg was not read as a plan.',
    why: 'not a plan: a cat',
  });
  expect(readLine('a.jpg', file('text_only', 'a text document.')).why).toBe('a text document');
  expect(readLine('a.jpg', undefined)).toEqual({
    line: 'a.jpg was not read as a plan.',
    why: 'it is not in the project',
  });
});
