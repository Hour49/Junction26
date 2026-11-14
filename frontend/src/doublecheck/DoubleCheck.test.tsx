import { readFileSync } from 'node:fs';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnswerView } from '../api';
import {
  answer,
  answerArea,
  answerRefused,
  drawing,
  error as errorBody,
  project,
} from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import type { PageViewerProps } from '../viewer/PageViewer';
import { DoubleCheck } from './DoubleCheck';
import {
  asking,
  check,
  doorMarks,
  doubtM2,
  doubtUnmarked,
  reasked,
  signedBy,
  takeoffWithDoor,
  withCheck,
} from './testing';

// The viewer is a props-recording double (as in SurveyorScreen.test.tsx).
const viewer = vi.hoisted(() => ({ props: null as PageViewerProps | null }));
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: PageViewerProps) => {
    viewer.props = props;
    return <div data-testid="viewer" />;
  },
}));

const pid = project.id;
const did = answer.drawing_id;
const PATH = {
  drawing: `GET /api/drawings/${did}`,
  review: `POST /api/drawings/${did}/review`,
  signoff: `POST /api/drawings/${did}/signoff`,
  ask: 'POST /api/ask',
};
const NAME_KEY = 'countersign.surveyorName';
const oneDoor = takeoffWithDoor({
  value: 1,
  status: 'edited',
  marks: doorMarks().map((m) => (m.id === 'm2' ? { ...m, state: 'rejected' as const } : m)),
});

function show(a: AnswerView = asking, routes: Record<string, unknown> = {}) {
  const onChanged = vi.fn<(a: AnswerView) => void>();
  const api = mockApi({ [PATH.drawing]: drawing, ...routes });
  const view = render(
    <DoubleCheck answer={a} projectId={pid} drawingId={did} onChanged={onChanged} />,
  );
  return { api, onChanged, ...view };
}
const panel = () => screen.getByRole('region', { name: 'Double-check' });
const button = (name: string | RegExp) => within(panel()).getByRole('button', { name });
const click = (name: string | RegExp) => {
  fireEvent.click(button(name));
};
const posts = (api: ReturnType<typeof mockApi>) => api.calls.filter((c) => c.method === 'POST');

beforeEach(() => {
  viewer.props = null;
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('DoubleCheck', () => {
  it('DC-1 renders nothing when certified, absent, refused or without a takeoff row', () => {
    for (const a of [
      answer, // no check field yet
      withCheck(answer, null),
      withCheck(answerRefused, check),
      withCheck({ ...answer, quantity: null }, check),
    ]) {
      const { container } = show(a);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('DC-2 says what it is not sure of, the reason, and each place with its why and readers', () => {
    show();
    const p = panel();
    expect(within(p).getByText('Please double-check')).toBeTruthy();
    expect(
      within(p).getByText("Please double-check: we're not sure about 1 of these doors."),
    ).toBeTruthy();
    expect(within(p).getByText(check.reason)).toBeTruthy();
    const list = within(p).getByRole('list', { name: 'Places to double-check' });
    const row = within(list).getByRole('listitem');
    expect(row.textContent).toContain('Mark 2');
    expect(row.textContent).toContain(doubtM2.why);
    // one line per reader, "<readerName(id)>: <sentence>", in the server's order
    expect([...row.querySelectorAll('.dc-reader')].map((e) => e.textContent)).toEqual([
      'PDF vector reader: a door',
      'image reader: nothing',
    ]);
  });

  it('DC-3 the viewer gets the marks, pages and disputed places; an uncounted place is listed', async () => {
    show(withCheck(answer, { ...check, disputed: [doubtM2, doubtUnmarked] }));
    await waitFor(() => {
      expect(viewer.props?.credit).toBe(drawing.credit);
    });
    expect(viewer.props?.marks).toEqual(answer.marks);
    expect(viewer.props?.pages).toEqual(answer.pages);
    expect(viewer.props?.disputed).toEqual([
      { markId: 'm2', page: 1, why: doubtM2.why },
      { page: 1, box: doubtUnmarked.box, why: doubtUnmarked.why },
    ]);
    expect(viewer.props?.fixMode).toBeFalsy();
    expect(within(panel()).getByText('Not counted, page 1')).toBeTruthy();
  });

  it('DC-4 hovering a place highlights its mark; a viewer click selects its row', () => {
    show();
    const place = button(/^Mark 2/);
    fireEvent.mouseEnter(place);
    expect(viewer.props?.highlighted).toBe('m2');
    fireEvent.mouseLeave(place);
    expect(viewer.props?.highlighted).toBeNull();
    act(() => {
      viewer.props?.onSelect?.('m2');
    });
    expect(button(/^Mark 2/).getAttribute('aria-current')).toBe('true');
    expect(viewer.props?.selected).toBe('m2');
  });

  it('DC-5 Looks right → confirm → one sign-off with settle, then a re-ask: checked by a person', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const { api, onChanged } = show(asking, {
      [PATH.signoff]: takeoffWithDoor({ status: 'signed', signed: signedBy }),
      [PATH.ask]: reasked,
    });
    click('Looks right');
    expect(within(panel()).getByText('Sign off 2 doors as')).toBeTruthy();
    expect(within(panel()).getByLabelText<HTMLInputElement>('Signing as').value).toBe('Ana');
    click('Confirm');
    await within(panel()).findByText('Checked by Ana, 2026-11-14 13:40 UTC');
    const [sign, ask] = posts(api);
    expect(sign?.url).toBe(`/api/drawings/${did}/signoff?project=${pid}`);
    expect(sign?.body).toEqual({ quantity: 'door', by: 'Ana', settle: true });
    expect(ask?.url).toBe('/api/ask');
    expect(ask?.body).toEqual({ question: answer.question, drawing_id: did, project_id: pid });
    expect(posts(api)).toHaveLength(2);
    expect(onChanged.mock.calls.at(-1)?.[0]).toEqual(reasked);
    expect(within(panel()).getByText('Checked by a person')).toBeTruthy();
  });

  it('DC-6 Confirm waits for a name; Back returns with nothing sent', () => {
    const { api } = show();
    click('Looks right');
    expect((button('Confirm') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(panel()).getByLabelText('Signing as'), { target: { value: 'Ana' } });
    expect((button('Confirm') as HTMLButtonElement).disabled).toBe(false);
    click('Back');
    expect(button('Looks right')).toBeTruthy();
    expect(posts(api)).toHaveLength(0);
  });

  it('DC-7 Fix it → Reject sends the edit, the value moves live, no re-ask', async () => {
    const { api, onChanged } = show(asking, { [PATH.review]: oneDoor });
    click('Fix it');
    expect(within(panel()).getByText('Fixing')).toBeTruthy();
    click('Reject mark 2');
    await waitFor(() => {
      expect(within(panel()).getByText('Value now:').parentElement?.textContent).toContain(
        '1 door',
      );
    });
    const [edit] = posts(api);
    expect(edit?.url).toBe(`/api/drawings/${did}/review?project=${pid}`);
    expect(edit?.body).toEqual({ quantity: 'door', action: 'reject', mark: 'm2' });
    const changed = onChanged.mock.calls.at(-1)?.[0] as AnswerView;
    expect(changed.answer).toBe(1);
    expect(changed.marks.find((m) => m.id === 'm2')?.state).toBe('rejected');
    expect(api.calls.some((c) => c.url === '/api/ask')).toBe(false);
    expect(button('Restore mark 2')).toBeTruthy();
  });

  it('DC-8 in fix mode a pick or "Add it here" adds a mark; an area answer cannot add', async () => {
    const both = withCheck(answer, { ...check, disputed: [doubtM2, doubtUnmarked] });
    const { api } = show(both, { [PATH.review]: oneDoor });
    click('Fix it');
    expect(viewer.props?.fixMode).toBe(true);
    act(() => {
      viewer.props?.onAddMark?.([0.1, 0.1, 0.13, 0.13], 1);
    });
    await waitFor(() => {
      expect(posts(api)).toHaveLength(1);
    });
    expect(posts(api)[0]?.body).toEqual({
      quantity: 'door',
      action: 'add',
      page: 1,
      box: [0.1, 0.1, 0.13, 0.13],
    });
    await waitFor(() => {
      expect((button('Add it here: page 1') as HTMLButtonElement).disabled).toBe(false);
    });
    click('Add it here: page 1');
    await waitFor(() => {
      expect(posts(api)).toHaveLength(2);
    });
    expect(posts(api)[1]?.body).toEqual({
      quantity: 'door',
      action: 'add',
      page: 1,
      box: doubtUnmarked.box,
    });
    cleanup();
    show(withCheck(answerArea, check));
    click('Fix it');
    expect(viewer.props?.fixMode).toBe(false);
    expect(viewer.props?.onAddMark).toBeUndefined();
    expect(within(panel()).queryByRole('button', { name: /^Add/ })).toBeNull();
  });

  it('DC-9 Done fixing → the confirm shows the new value and sends one sign-off', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const { api } = show(asking, {
      [PATH.review]: oneDoor,
      [PATH.signoff]: takeoffWithDoor({ value: 1, status: 'signed', signed: signedBy }),
      [PATH.ask]: reasked,
    });
    click('Fix it');
    click('Reject mark 2');
    await waitFor(() => {
      expect((button('Done fixing') as HTMLButtonElement).disabled).toBe(false);
    });
    click('Done fixing');
    expect(within(panel()).getByText('Sign off 1 door as')).toBeTruthy();
    click('Confirm');
    await within(panel()).findByText('Checked by a person');
    expect(posts(api).map((c) => c.url.split('?')[0])).toEqual([
      `/api/drawings/${did}/review`,
      `/api/drawings/${did}/signoff`,
      '/api/ask',
    ]);
  });

  it('DC-10 a signed answer shows Checked by a person and no request', () => {
    show(reasked);
    expect(within(panel()).getByText('Checked by a person')).toBeTruthy();
    expect(within(panel()).getByText('Checked by Ana, 2026-11-14 13:40 UTC')).toBeTruthy();
    const link = within(panel()).getByRole('link', { name: 'Open in the surveyor workspace' });
    expect(link.getAttribute('href')).toBe(`#/p/${pid}/d/${did}/surveyor?q=door`);
    expect(within(panel()).queryByRole('button', { name: 'Looks right' })).toBeNull();
    expect(within(panel()).queryByRole('button', { name: 'Fix it' })).toBeNull();
  });

  it('DC-11 a 409 says someone signed it already and re-asks', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const { onChanged } = show(asking, {
      [PATH.signoff]: reply(409, { ...errorBody, code: 'signed', detail: 'signed off' }),
      [PATH.ask]: reasked,
    });
    click('Looks right');
    click('Confirm');
    const alert = await within(panel()).findByRole('alert');
    expect(alert.textContent).toBe(
      'Someone signed this off already. Undo the sign-off in the surveyor workspace to change it.',
    );
    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(reasked);
    });
  });

  it('DC-12 a failed sign-off shows the error; Confirm again resends it', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    let fail = true;
    const { api } = show(asking, {
      [PATH.signoff]: () =>
        fail
          ? reply(500, { ...errorBody, detail: 'disk full' })
          : takeoffWithDoor({ signed: signedBy, status: 'signed' }),
      [PATH.ask]: reasked,
    });
    click('Looks right');
    click('Confirm');
    expect((await within(panel()).findByRole('alert')).textContent).toContain('disk full');
    fail = false;
    click('Confirm');
    await within(panel()).findByText('Checked by a person');
    expect(posts(api).filter((c) => c.url.includes('/signoff'))).toHaveLength(2);
  });

  it('DC-13 while a request is in flight every button is disabled and Saving… shows', async () => {
    show(asking, { [PATH.review]: never() });
    click('Fix it');
    click('Reject mark 2');
    expect(within(panel()).getByRole('status').textContent).toBe('Saving…');
    for (const b of within(panel()).getAllByRole('button')) {
      expect((b as HTMLButtonElement).disabled).toBe(true);
    }
    await Promise.resolve();
  });

  it('DC-14 why, reason and reader ids render as text', () => {
    const evil = '<img src=x onerror=alert(1)>';
    const { container } = show(
      withCheck(answer, {
        reason: evil,
        disputed: [{ ...doubtM2, why: evil, readers: { [evil]: evil } }],
      }),
    );
    expect(within(panel()).getAllByText(evil, { exact: false }).length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('img')).toBeNull();
  });

  it('DC-15 doublecheck.css holds no colour literal and no other font', () => {
    const css = readFileSync('src/doublecheck/doublecheck.css', 'utf8'); // vitest runs in frontend/
    expect(css.length).toBeGreaterThan(100);
    expect(css.split('\n').filter((l) => /#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/i.test(l))).toEqual(
      [],
    );
    for (const m of css.matchAll(/font-family:\s*([^;]+);/g))
      expect(['var(--v-font)', 'ui-monospace, Menlo, monospace']).toContain(m[1]?.trim());
  });

  it('DC-16 Cancel after an edit keeps it and says so, with the workspace link', async () => {
    show(asking, { [PATH.review]: oneDoor });
    click('Fix it');
    click('Reject mark 2');
    await waitFor(() => {
      expect((button('Cancel') as HTMLButtonElement).disabled).toBe(false);
    });
    click('Cancel');
    expect(
      within(panel()).getByText(
        'Your edits are kept; Reset in the surveyor workspace undoes them.',
      ),
    ).toBeTruthy();
    expect(
      within(panel()).getByRole('link', { name: 'Open in the surveyor workspace' }),
    ).toBeTruthy();
    expect(button('Looks right')).toBeTruthy();
  });

  it('DC-17 a drawing error shows a line with Retry; the panel still works', async () => {
    let fail = true;
    const { api } = show(asking, {
      [PATH.drawing]: () => (fail ? reply(500, { ...errorBody, detail: 'boom' }) : drawing),
    });
    const alert = await within(panel()).findByRole('alert');
    expect(alert.textContent).toContain('boom');
    expect(button('Looks right')).toBeTruthy();
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await waitFor(() => {
      expect(viewer.props?.credit).toBe(drawing.credit);
    });
    expect(api.calls.filter((c) => c.url.startsWith(`/api/drawings/${did}?`))).toHaveLength(2);
  });
});
