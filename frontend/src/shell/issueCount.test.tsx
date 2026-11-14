import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Issue } from '../api';
import { error, project, projectIssues } from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import { issuesChanged, useIssuesToAnswer } from './issueCount';

const PID = projectIssues.project_id;
const GET = `GET /api/projects/${PID}/issues`;
const PROJECT = `GET /api/projects/${PID}`;
const base: Issue = { ...(projectIssues.issues[0] as Issue), kind: 'reading_flag', answer: null };
const issue = (id: string, severity: Issue['severity'], state: Issue['state']): Issue => ({
  ...base,
  id,
  severity,
  state,
});
/** DOC-12: three to answer (a failed rule counts), plus a settled one, a note, a conflict and an answered one. */
const issues = [
  issue('a', 'needs_person', 'open'),
  issue('b', 'needs_person', 'open'),
  issue('e', 'fails_rule', 'open'),
  issue('c', 'needs_person', 'settled'),
  issue('d', 'note', 'open'),
  { ...issue('f', 'needs_person', 'open'), kind: 'conflict' as const },
  {
    ...issue('g', 'needs_person', 'open'),
    answer: { text: 'Hall', by: 'Ana', at: '2026-11-14T08:05:00Z' },
  },
];
const list = { ...projectIssues, issues };
const done = (toAnswer: number | null) => ({
  ...project,
  id: PID,
  state: 'done',
  issues_to_answer: toAnswer,
});

afterEach(cleanup);

describe('issues to answer', () => {
  it("SH-78 the server's issues_to_answer, from the project alone (no issues request)", async () => {
    const api = mockApi({ [PROJECT]: done(2) });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    expect(result.current).toBeNull();
    await waitFor(() => {
      expect(result.current).toBe(2);
    });
    expect(api.calls.map((c) => `${c.method} ${c.url}`)).toEqual([PROJECT]);
  });

  it('SH-78 without issues_to_answer: needsYou over the issues, an Issue.answer counts as answered', async () => {
    const api = mockApi({ [PROJECT]: done(null), [GET]: list });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    await waitFor(() => {
      expect(result.current).toBe(3);
    });
    expect(api.calls).toHaveLength(2);
  });

  it("SH-88 with a pack: needsYou over the pack's issues, issues_to_answer ignored, re-asked on issuesChanged", async () => {
    let rows = issues;
    const api = mockApi({
      [PROJECT]: done(0),
      [GET]: (c: { url: string }) =>
        c.url.endsWith('?pack=ch-zh') ? { ...list, issues: rows } : list,
    });
    const { result } = renderHook(() => useIssuesToAnswer(PID, undefined, 'ch-zh'));
    await waitFor(() => {
      expect(result.current).toBe(3);
    });
    rows = issues.filter((i) => i.id !== 'e');
    act(() => {
      issuesChanged(PID);
    });
    await waitFor(() => {
      expect(result.current).toBe(2);
    });
    expect(api.calls.filter((c) => c.url.endsWith('?pack=ch-zh'))).toHaveLength(2);
  });

  it('SH-87 issuesChanged(projectId) asks again (after an answer); another project is left alone', async () => {
    let toAnswer = 2;
    const api = mockApi({ [PROJECT]: () => done(toAnswer) });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    await waitFor(() => {
      expect(result.current).toBe(2);
    });
    toAnswer = 1;
    act(() => {
      issuesChanged('other');
    });
    expect(api.calls).toHaveLength(1);
    act(() => {
      issuesChanged(PID);
    });
    await waitFor(() => {
      expect(result.current).toBe(1);
    });
    expect(api.calls).toHaveLength(2);
  });

  it('SH-78 the hook asks again when the reload key changes, and not for a null project', async () => {
    const api = mockApi({ [PROJECT]: done(2) });
    const { result, rerender } = renderHook(({ key }) => useIssuesToAnswer(PID, key), {
      initialProps: { key: 'a' },
    });
    await waitFor(() => {
      expect(result.current).toBe(2);
    });
    rerender({ key: 'b' });
    await waitFor(() => {
      expect(api.calls).toHaveLength(2);
    });
    const none = renderHook(() => useIssuesToAnswer(null));
    expect(none.result.current).toBeNull();
    expect(api.calls).toHaveLength(2);
  });

  it('SH-78 a project or issues error, and a load in flight, give null', async () => {
    for (const routes of [
      { [PROJECT]: reply(500, error) },
      { [PROJECT]: done(null), [GET]: reply(409, { ...error, code: 'not-ready' }) },
    ]) {
      const api = mockApi(routes);
      const { result, unmount } = renderHook(() => useIssuesToAnswer(PID));
      await waitFor(() => {
        expect(api.calls).toHaveLength(Object.keys(routes).length);
      });
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current).toBeNull();
      unmount();
    }
    mockApi({ [PROJECT]: never() });
    expect(renderHook(() => useIssuesToAnswer(PID)).result.current).toBeNull();
  });

  it('SH-78 nothing asked about issues while the ingest runs; the count once the project is done', async () => {
    let state = 'running';
    const api = mockApi({ [PROJECT]: () => ({ ...done(3), state }) });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    await waitFor(() => {
      expect(api.calls).toHaveLength(1);
    });
    expect(result.current).toBeNull();
    state = 'done';
    await waitFor(
      () => {
        expect(result.current).toBe(3);
      },
      { timeout: 3000 },
    );
  });

  it('SH-78 a failed project gives null and asks no issues', async () => {
    const api = mockApi({ [PROJECT]: { ...done(null), state: 'failed' } });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    await waitFor(() => {
      expect(api.calls).toHaveLength(1);
    });
    expect(result.current).toBeNull();
  });
});
