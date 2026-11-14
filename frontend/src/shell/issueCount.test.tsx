import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Issue } from '../api';
import { error, projectIssues } from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import { answerOf, setAnswer } from './issueAnswers';
import { useIssuesToAnswer } from './issueCount';

const PID = projectIssues.project_id;
const GET = `GET /api/projects/${PID}/issues`;
const base: Issue = { ...(projectIssues.issues[0] as Issue), kind: 'reading_flag' };
const issue = (id: string, severity: Issue['severity'], state: Issue['state']): Issue => ({
  ...base,
  id,
  severity,
  state,
});
/** DOC-12: three to answer (a failed rule counts), plus a settled one, a note and a conflict that never count. */
const issues = [
  issue('a', 'needs_person', 'open'),
  issue('b', 'needs_person', 'open'),
  issue('e', 'fails_rule', 'open'),
  issue('c', 'needs_person', 'settled'),
  issue('d', 'note', 'open'),
  { ...issue('f', 'needs_person', 'open'), kind: 'conflict' as const },
];
const list = { ...projectIssues, issues };

afterEach(() => {
  cleanup();
  for (const id of ['a', 'b']) setAnswer(PID, id, null);
});

describe('issues to answer', () => {
  it('SH-78 the store: setAnswer and answerOf per project; null clears', () => {
    expect(answerOf(PID, 'a')).toBeNull();
    setAnswer(PID, 'a', 'Bedroom');
    expect(answerOf(PID, 'a')).toBe('Bedroom');
    expect(answerOf('other', 'a')).toBeNull();
    expect(answerOf(PID, 'b')).toBeNull();
    setAnswer(PID, 'a', null);
    expect(answerOf(PID, 'a')).toBeNull();
  });

  it('SH-78 the hook: one request, an answer lowers the count without a new request, clearing raises it', async () => {
    const api = mockApi({ [GET]: list });
    const { result } = renderHook(() => useIssuesToAnswer(PID));
    expect(result.current).toBeNull();
    await waitFor(() => {
      expect(result.current).toBe(3);
    });
    act(() => {
      setAnswer(PID, 'a', 'Bedroom');
    });
    expect(result.current).toBe(2);
    act(() => {
      setAnswer(PID, 'a', null);
    });
    expect(result.current).toBe(3);
    expect(api.calls.map((c) => `${c.method} ${c.url}`)).toEqual([GET]);
  });

  it('SH-78 the hook asks again when the reload key changes, and not for a null project', async () => {
    const api = mockApi({ [GET]: list });
    const { result, rerender } = renderHook(({ key }) => useIssuesToAnswer(PID, key), {
      initialProps: { key: 'a' },
    });
    await waitFor(() => {
      expect(result.current).toBe(3);
    });
    rerender({ key: 'b' });
    await waitFor(() => {
      expect(api.calls).toHaveLength(2);
    });
    const none = renderHook(() => useIssuesToAnswer(null));
    expect(none.result.current).toBeNull();
    expect(api.calls).toHaveLength(2);
  });

  it('SH-78 a 409, a 500 and a load in flight give null', async () => {
    for (const body of [reply(409, { ...error, code: 'not-ready' }), reply(500, error)]) {
      const api = mockApi({ [GET]: body });
      const { result, unmount } = renderHook(() => useIssuesToAnswer(PID));
      await waitFor(() => {
        expect(api.calls).toHaveLength(1);
      });
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current).toBeNull();
      unmount();
    }
    mockApi({ [GET]: never() });
    expect(renderHook(() => useIssuesToAnswer(PID)).result.current).toBeNull();
  });
});
