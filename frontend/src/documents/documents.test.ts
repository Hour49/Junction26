import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { drawing, projectIssues, projectReviewResolved, resolving } from '../api/fixtures';
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
// resolver.md: no Issue fixture carries `resolved`; the conflict issue with the review fixtures' replies
const picked: Issue = {
  ...conflict,
  id: 'picked',
  state: 'open',
  severity: 'note',
  resolved: projectReviewResolved.conflicts[0]?.resolved,
};
const cannotTell: Issue = {
  ...conflict,
  id: 'cannot',
  state: 'open',
  severity: 'needs_person',
  resolved: resolving.review.conflicts[0]?.resolved,
};

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

  it('RS-30 RS-31 a conflict Carbon looked at is listed; its can-not-tell is counted, its pick is not', () => {
    expect(documentIssues([conflict, picked, cannotTell]).map((r) => r.issue.id)).toEqual([
      'cannot',
      'picked',
    ]);
    expect(needsYou([picked])).toBe(0);
    expect(needsYou([cannotTell])).toBe(1);
    expect(needsYou([{ ...cannotTell, state: 'settled' }])).toBe(0);
    expect(pillOf(picked)).toEqual({ word: 'Note', tone: '' });
    expect(pillOf(cannotTell)).toEqual({ word: 'Needs a person', tone: 'warn' });
    expect(isAnswerable(cannotTell)).toBe(false); // settled on its conflict card, not here
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

  it('DOC-12 needsYou: answerable, open, without Issue.answer, notes excluded', () => {
    const all = [conflict, located, aside, needs, fails, unsure, unrelatedNote];
    const answer = { text: '1:100', by: 'Ana', at: '2026-11-14T08:05:00Z' };
    expect(needsYou(all)).toBe(3); // needs, fails, unsure
    expect(needsYou(all.map((i) => (i.id === 'needs' ? { ...i, answer } : i)))).toBe(2);
    expect(needsYou([...all, { ...unsure, id: 'done', state: 'settled' }])).toBe(3);
    expect(needsYou([{ ...conflict, severity: 'needs_person', state: 'open' }])).toBe(0);
    expect(needsYou([])).toBe(0);
  });

  it('pillOf: note, severity while open, Answered once answered or settled', () => {
    const answer = { text: '1:100', by: 'Ana', at: '2026-11-14T08:05:00Z' };
    expect(pillOf(located)).toEqual({ word: 'Note', tone: '' });
    expect(pillOf(needs)).toEqual({ word: 'Needs a person', tone: 'warn' });
    expect(pillOf(fails)).toEqual({ word: 'Fails a rule', tone: 'warn' });
    expect(pillOf({ ...needs, answer })).toEqual({ word: 'Answered', tone: 'ok' });
    expect(pillOf({ ...unsure, state: 'settled' })).toEqual({
      word: 'Answered',
      tone: 'ok',
    });
  });

  it('DOC-6 issueSource: page and one place; no box, no page, a file only, nothing', () => {
    const page = drawing.pages[0];
    const withDrawing = { ...needs, page: page?.page ?? 1 };
    expect(issueSource(withDrawing, PID, drawing)).toEqual({
      name: 'Plan image 1', // #229 drawing_name, not the file
      page,
      places: [
        { label: 'How it was read', box: [0.1, 0.2, 0.3, 0.4], polygon: withDrawing.polygon },
      ],
    });
    expect(issueSource({ ...withDrawing, drawing_name: null }, PID, drawing)?.name).toBe(
      withDrawing.file,
    ); // no drawing name: the file
    expect(issueSource({ ...withDrawing, label: null }, PID, drawing)?.places[0]?.label).toBe(
      withDrawing.why,
    ); // no Issue.label: the why
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
      shortReason({
        state: 'flagged',
        reason: 'not read: this setup has no reader for the image route',
      }),
    ).toBeNull();
    expect(
      shortReason({ state: 'text_only', reason: 'a text document, not a drawing (page 1)' }),
    ).toBeNull();
    expect(shortReason({ state: 'set_aside', reason: '' })).toBeNull();
  });

  it('DOC-15 the Documents tab names no colour literal (Tailwind classes use the theme tokens)', () => {
    for (const file of ['DocumentsScreen.tsx', 'DocumentLists.tsx', 'IssueCard.tsx', 'ui.ts']) {
      // only class strings: comments cite issues as #223
      const source = readFileSync(`src/documents/${file}`, 'utf8').replace(
        /\/\/.*|\/\*[\s\S]*?\*\//g,
        '',
      );
      expect(source, file).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    }
  });
});
