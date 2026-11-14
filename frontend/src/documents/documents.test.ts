import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { drawing, projectIssues } from '../api/fixtures';
import type { Issue } from '../api';
import {
  documentIssues,
  isAnswerable,
  issueSource,
  needsYou,
  pillOf,
  shortReason,
} from './documents';

const PID = projectIssues.project_id;
const base = projectIssues.issues;
const byKind = (kind: string) => {
  const found = base.find((i) => i.kind === kind);
  if (!found) throw new Error(kind);
  return found;
};
// Variants of the fixture's issues (documents.md "States"): the fixture holds notes only.
const conflict = byKind('conflict');
const located = byKind('reading_flag');
const aside = byKind('set_aside');
const needs: Issue = {
  ...located,
  id: 'needs',
  severity: 'needs_person',
  box: [0.1, 0.2, 0.3, 0.4],
};
const fails: Issue = { ...located, id: 'fails', kind: 'code_check_failed', severity: 'fails_rule' };
const unsure: Issue = { ...aside, id: 'unsure', kind: 'unrelated_file', severity: 'needs_person' };
const unrelatedNote: Issue = { ...aside, id: 'unote', kind: 'unrelated_file', severity: 'note' };
const none: ReadonlyMap<string, string> = new Map();

describe('documents.ts', () => {
  it('DOC-3 leaves conflicts out, groups by severity, numbers by position in this list', () => {
    const rows = documentIssues([conflict, located, needs, fails, aside]);
    expect(rows.map((r) => [r.n, r.issue.id])).toEqual([
      [1, 'fails'],
      [2, 'needs'],
      [3, located.id],
      [4, aside.id],
    ]);
  });

  it('answerable: not a conflict, and not a note unless it is an unrelated_file', () => {
    expect([conflict, located, needs, fails, unsure, unrelatedNote].map(isAnswerable)).toEqual([
      false,
      false,
      true,
      true,
      true,
      true,
    ]);
  });

  it('DOC-12 needsYou: answerable, open, not answered, notes excluded', () => {
    const all = [conflict, located, aside, needs, fails, unsure, unrelatedNote];
    expect(needsYou(all, none)).toBe(3); // needs, fails, unsure
    expect(needsYou(all, new Map([['needs', '1:100']]))).toBe(2);
    expect(needsYou([...all, { ...unsure, id: 'done', state: 'settled' }], none)).toBe(3);
    expect(needsYou([{ ...conflict, severity: 'needs_person', state: 'open' }], none)).toBe(0);
    expect(needsYou([], none)).toBe(0);
  });

  it('pillOf: note, severity while open, Answered once answered or settled', () => {
    expect(pillOf(located, false)).toEqual({ word: 'Note', tone: '' });
    expect(pillOf(needs, false)).toEqual({ word: 'Needs a person', tone: 'warn' });
    expect(pillOf(fails, false)).toEqual({ word: 'Fails a rule', tone: 'warn' });
    expect(pillOf(needs, true)).toEqual({ word: 'Answered', tone: 'ok' });
    expect(pillOf({ ...unsure, state: 'settled' }, false)).toEqual({
      word: 'Answered',
      tone: 'ok',
    });
  });

  it('DOC-6 issueSource: page and one place; no box, no page, a file only, nothing', () => {
    const page = drawing.pages[0];
    const withDrawing = { ...needs, page: page?.page ?? 1 };
    expect(issueSource(withDrawing, PID, drawing)).toEqual({
      name: withDrawing.file,
      page,
      places: [{ label: withDrawing.why, box: [0.1, 0.2, 0.3, 0.4], polygon: withDrawing.polygon }],
    });
    expect(issueSource({ ...withDrawing, box: null, polygon: null }, PID, drawing)?.places).toEqual(
      [],
    );
    expect(issueSource({ ...withDrawing, page: null }, PID, drawing)?.page).toBeNull();
    expect(issueSource(withDrawing, PID, null)?.page).toBeNull(); // drawing not loaded or failed
    const photo = { kind: 'photo' } as const;
    expect(issueSource(aside, PID, null, photo)).toEqual({
      name: aside.file,
      page: null,
      image: `/api/projects/${PID}/files/${String(aside.file_id)}/preview.png?width=400`,
      places: [],
    });
    expect(issueSource(aside, PID, null, { kind: 'dxf' })).toBeNull(); // no preview.png for a DXF
    expect(issueSource(aside, PID, null, undefined)).toBeNull();
    expect(issueSource({ ...aside, file_id: null }, PID, null, photo)).toBeNull();
  });

  it('DOC-17 shortReason: a set-aside reason without its trailing parenthetical; nothing for other states', () => {
    expect(
      shortReason({
        state: 'set_aside',
        reason: 'a photo, not of a drawing (1600x1200 px, 15% white)',
      }),
    ).toBe('a photo, not of a drawing');
    expect(shortReason({ state: 'set_aside', reason: 'not a drawing' })).toBe('not a drawing');
    expect(
      shortReason({ state: 'ready', reason: 'read on the drawn PDF route: 7 elements' }),
    ).toBeNull();
    expect(
      shortReason({ state: 'flagged', reason: 'no reader for the image route yet' }),
    ).toBeNull();
    expect(
      shortReason({ state: 'text_only', reason: 'a text document, not a drawing (page 1)' }),
    ).toBeNull();
    expect(shortReason({ state: 'set_aside', reason: '' })).toBeNull();
  });

  it('DOC-15 documents.css has no colour literal', () => {
    const css = readFileSync('src/documents/documents.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });
});
