import { readFileSync } from 'node:fs';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { methodName, type MarkView, type Row, type Takeoff } from '../api';
import {
  drawing,
  error as errorBody,
  project,
  projectReview,
  reviewRequests,
  signoffRequest,
  takeoff,
} from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import type { PageViewerProps } from '../viewer/PageViewer';
import { SurveyorScreen } from './SurveyorScreen';
import { markWords, statusText } from './words';

// The viewer is a test double: it records its props so a test can read them and call its callbacks.
const viewer = vi.hoisted(() => ({ props: null as PageViewerProps | null }));
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: PageViewerProps) => {
    viewer.props = props;
    return <div data-testid="viewer" />;
  },
}));

const did = takeoff.drawing_id;
const pid = project.id;
const PATH = {
  takeoff: `GET /api/drawings/${did}/takeoff`,
  drawing: `GET /api/drawings/${did}`,
  review: `GET /api/projects/${pid}/review`,
  edit: `POST /api/drawings/${did}/review`,
  sign: `POST /api/drawings/${did}/signoff`,
};
const CONFLICT = 'area:room|name=1.01';

function nth<T>(xs: readonly T[], i: number): T {
  const x = xs[i];
  if (x === undefined) throw new Error(`no item ${String(i)}`);
  return x;
}
const rowOf = (t: Takeoff, key: string): Row => {
  const found = t.quantities.find((q) => q.key === key);
  if (!found) throw new Error(`no row ${key}`);
  return found;
};
/** The takeoff fixture with one row changed. */
function derive(key: string, patch: Partial<Row>, base: Takeoff = takeoff): Takeoff {
  return {
    ...base,
    quantities: base.quantities.map((q) => (q.key === key ? { ...q, ...patch } : q)),
  };
}
const conflictOf = (key: string) => {
  const found = rowOf(takeoff, key).conflict;
  if (!found) throw new Error(`no conflict on ${key}`);
  return found;
};
const doorMarks = rowOf(takeoff, 'door').marks;
const markAt = (i: number, patch: Partial<MarkView>): MarkView => ({
  ...nth(doorMarks, i),
  ...patch,
});
const signedDoor = derive('door', {
  status: 'signed',
  signed: { by: 'Ana', at: '2026-11-14T01:40:00Z', value: 2 },
});
const needsPerson = derive(CONFLICT, {
  needs_person: true,
  conflict: { ...conflictOf(CONFLICT), resolution: null },
});

function show(query = '', routes: Record<string, unknown> = {}) {
  const api = mockApi({
    [PATH.takeoff]: takeoff,
    [PATH.drawing]: drawing,
    [PATH.review]: projectReview,
    ...routes,
  });
  render(<SurveyorScreen projectId={pid} drawingId={did} query={new URLSearchParams(query)} />);
  return api;
}
const ready = () => screen.findByRole('table', { name: 'To review' });
const detail = () => screen.getByRole('region', { name: 'Selected quantity' });
const pick = (label: string) => {
  fireEvent.click(screen.getByRole('button', { name: label }));
};
const posted = (api: ReturnType<typeof mockApi>, path: string) =>
  api.calls.filter((c) => c.method === 'POST' && c.url.startsWith(path.split(' ')[1] ?? ''));

beforeEach(() => {
  viewer.props = null;
  window.location.hash = `#/p/${pid}/d/${did}/surveyor`;
  localStorage.clear();
});
afterEach(cleanup);

describe('loading and routing', () => {
  it('SV-1 sends the three loads and shows loading until takeoff and drawing answer', async () => {
    const api = show('', { [PATH.takeoff]: never() });
    expect(screen.getByText('Loading the takeoff…')).toBeTruthy();
    await waitFor(() => {
      expect(api.calls.map((c) => c.url)).toEqual(
        expect.arrayContaining([
          `/api/drawings/${did}/takeoff?project=${pid}`,
          `/api/drawings/${did}?project=${pid}`,
          `/api/projects/${pid}/review`,
        ]),
      );
    });
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('SV-2 the table shows exactly the rows of quantities', async () => {
    show();
    await ready();
    for (const q of takeoff.quantities) {
      expect(screen.getAllByRole('button', { name: q.label })).toHaveLength(1);
    }
    expect(screen.getAllByRole('row').filter((r) => r.dataset.key)).toHaveLength(3);
  });

  it('SV-3 groups the review queue first, ignoring queue keys with no row', async () => {
    show();
    const review = await ready();
    const keys = (t: HTMLElement) =>
      within(t)
        .getAllByRole('row')
        .map((r) => r.dataset.key)
        .filter(Boolean);
    expect(keys(review)).toEqual([CONFLICT]);
    expect(keys(screen.getByRole('table', { name: 'All other quantities' }))).toEqual([
      'door',
      'area:room|indoor',
    ]);
  });

  it('SV-4 selects ?q=, else the first queue row, else the default', async () => {
    show();
    await ready();
    expect(within(detail()).getByRole('heading').textContent).toContain('area of room (name 1.01)');
    cleanup();
    show(new URLSearchParams({ q: 'door' }).toString());
    await ready();
    expect(within(detail()).getByRole('heading').textContent).toContain('door count');
    cleanup();
    show('q=nothing');
    await ready();
    expect(within(detail()).getByRole('heading').textContent).toContain('area of room (name 1.01)');
  });

  it('SV-5 selecting a row replaces ?q= without a history entry', async () => {
    show();
    await ready();
    const before = history.length;
    pick('door count');
    expect(new URLSearchParams(location.hash.split('?')[1]).get('q')).toBe('door');
    expect(history.length).toBe(before);
  });

  it('SV-6 a row is a focusable button that Enter selects', async () => {
    show();
    await ready();
    const button = screen.getByRole('button', { name: 'door count' });
    button.focus();
    expect(document.activeElement).toBe(button);
    expect(button.tagName).toBe('BUTTON'); // a native button: Enter and Space click it
    fireEvent.click(button);
    expect(within(detail()).getByRole('heading').textContent).toContain('door count');
  });
});

describe('table and detail', () => {
  it('SV-7 status words', async () => {
    const words = (status: Row['status']) => statusText({ status, needs_person: false });
    expect(
      ['signed', 'conflict', 'estimate', 'edited', 'agree', 'single'].map((s) =>
        words(s as Row['status']),
      ),
    ).toEqual([
      'Verified',
      'Methods disagree',
      'Estimate',
      'Changed in review',
      'Two methods agree',
      'One method',
    ]);
    show();
    await ready();
    const cells = takeoff.quantities.map(
      (q) =>
        screen.getByRole('row', { name: new RegExp(q.label.replace(/[()]/g, '\\$&')) }).textContent,
    );
    expect(nth(cells, 0)).toContain('Methods disagree');
    expect(nth(cells, 1)).toContain('One method');
    expect(nth(cells, 2)).toContain('One method');
  });

  it('SV-8 needs_person shows "needs you" in the row and the detail', async () => {
    show('', { [PATH.takeoff]: needsPerson });
    const review = await ready();
    expect(within(review).getByRole('row', { name: /1\.01/ }).textContent).toContain('needs you');
    expect(detail().textContent).toContain('needs you');
  });

  it('SV-9 values are the API value, formatted, never a client sum', async () => {
    show();
    await ready();
    expect(screen.getByRole('row', { name: /door count/ }).textContent).toContain('2');
    expect(screen.getByRole('row', { name: /door count/ }).textContent).not.toContain('count2 ');
    const indoor = screen.getByRole('row', { name: /indoor/ }).textContent;
    expect(indoor).toContain('59.87 m²');
    expect(indoor).not.toContain('32.49');
  });

  it('SV-10 a changed value: struck-through original in the table, "was … at ingest" in the detail', async () => {
    show('q=door', { [PATH.takeoff]: derive('door', { value: 3 }) });
    await ready();
    const row = screen.getByRole('row', { name: /door count/ });
    expect(row.querySelector('s')?.textContent).toBe('2');
    expect(detail().textContent).toContain('was 2 at ingest');
    expect(detail().querySelector('s')).toBeNull();
    expect(detail().querySelector('.sv-value')?.textContent).toBe('3 was 2 at ingest');
    pick('area of room (indoor)');
    expect(detail().textContent).not.toContain('at ingest');
    expect(screen.getByRole('row', { name: /indoor/ }).querySelector('s')).toBeNull();
  });

  it('SV-11 both methods show in the table and the detail when set', async () => {
    show();
    await ready();
    const both = `${methodName('polygon_x_scale')} 22.40 m² · ${methodName('printed_label')} 30.00 m²`;
    expect(screen.getByRole('row', { name: /1\.01/ }).textContent).toContain(both);
    expect(detail().textContent).toContain(methodName('polygon_x_scale'));
    expect(screen.getByRole('row', { name: /door count/ }).textContent).not.toContain('·');
  });

  it('SV-12 conflict values lettered, and the rule that kept one or the needs-person text', async () => {
    show();
    await ready();
    const text = detail().textContent;
    expect(text).toContain(`A: 22.40 m² ${methodName('polygon_x_scale')}`);
    expect(text).toContain(`B: 30.00 m² ${methodName('printed_label')}`);
    expect(text).toContain(
      "Kept by rule: the printed label over the outline at the sheet's scale → 30.00 m²",
    );
    cleanup();
    show('', { [PATH.takeoff]: needsPerson });
    await ready();
    expect(detail().textContent).toContain('No rule decides. Settle a value before signing off.');
  });

  it('SV-13 the viewer gets the row conflict and unit', async () => {
    show();
    await ready();
    expect(viewer.props?.conflict).toEqual(rowOf(takeoff, CONFLICT).conflict);
    expect(viewer.props?.unit).toBe('m2');
    pick('door count');
    expect(viewer.props?.conflict).toBeNull();
  });

  it('SV-14 estimate, conflict note and derived show as text', async () => {
    show('', {
      [PATH.takeoff]: derive(CONFLICT, {
        estimate: 'scale read from a scale bar',
        conflict: { ...conflictOf(CONFLICT), note: 'labels overlap', derived: 'from room 1.02' },
      }),
    });
    await ready();
    const text = detail().textContent;
    expect(text).toContain('Estimate: scale read from a scale bar');
    expect(text).toContain('labels overlap');
    expect(text).toContain('from room 1.02');
  });

  it('SV-15 the counting rule text', async () => {
    show();
    await ready();
    expect(detail().textContent).toContain(`Counting rule: ${rowOf(takeoff, CONFLICT).rule.text}`);
  });

  it('SV-16 progress counts signed rows', async () => {
    show();
    await ready();
    expect(screen.getByText('0 of 3 quantities signed off')).toBeTruthy();
    cleanup();
    show('', { [PATH.takeoff]: signedDoor });
    await ready();
    expect(screen.getByText('1 of 3 quantities signed off')).toBeTruthy();
  });
});

describe('marks', () => {
  const marks = () => within(detail()).getByRole('list', { name: 'Marks' });

  it('SV-17 one mark row per mark with number, label and area value', async () => {
    show('q=door');
    await ready();
    const items = within(marks()).getAllByRole('listitem');
    expect(items.map((i) => i.querySelector('.sv-sign')?.textContent)).toEqual(['1', '2']);
    pick('area of room (indoor)');
    const area = within(marks())
      .getAllByRole('listitem')
      .map((i) => i.textContent);
    expect(nth(area, 0)).toContain('Küche');
    expect(nth(area, 0)).toContain('30.00 m²');
    expect(nth(area, 1)).toContain('Reduit');
    expect(nth(area, 1)).toContain('2.49 m²');
  });

  it('SV-18 signs and words per mark state', async () => {
    const reason = 'outdoor room';
    const four = derive('door', {
      marks: [
        markAt(0, { state: 'rejected', n: null }),
        markAt(1, { id: 'x1', state: 'excluded', n: null, reason }),
        markAt(1, { id: 'a1', state: 'added', n: 3, label: null, ref: null }),
        markAt(1, { id: 'x2', state: 'counted', n: 2, reason }),
      ],
    });
    expect(markWords(nth(rowOf(four, 'door').marks, 0), 'count').sign).toBe('×');
    show('q=door', { [PATH.takeoff]: four });
    await ready();
    const items = within(marks()).getAllByRole('listitem');
    expect(items.map((i) => i.querySelector('.sv-sign')?.textContent)).toEqual([
      '×',
      '–',
      '+3',
      '2',
    ]);
    expect(nth(items, 1).textContent).toContain('left out by the rule: outdoor room');
    expect(nth(items, 3).textContent).toContain('counted in by a surveyor');
  });

  it('SV-19 the viewer gets the drawing and the selected row', async () => {
    show();
    await ready();
    expect(viewer.props?.file).toBe(drawing.file);
    expect(viewer.props?.pages).toEqual(drawing.pages);
    expect(viewer.props?.credit).toBe(drawing.credit);
    expect(viewer.props?.marks).toEqual(rowOf(takeoff, CONFLICT).marks);
    pick('door count');
    expect(viewer.props?.marks).toEqual(doorMarks);
    expect(viewer.props?.unlocated).toEqual(rowOf(takeoff, 'door').unlocated);
  });

  it('SV-20 hover, focus and select tie the mark list and the viewer together', async () => {
    show('q=door');
    await ready();
    const items = within(marks()).getAllByRole('listitem');
    fireEvent.mouseEnter(nth(items, 1));
    expect(viewer.props?.highlighted).toBe('m2');
    act(() => viewer.props?.onHover?.('m1'));
    expect(nth(within(marks()).getAllByRole('listitem'), 0).className).toContain('sv-hot');
    act(() => viewer.props?.onSelect?.('m2'));
    expect(viewer.props?.selected).toBe('m2');
    expect(document.activeElement).toBe(nth(within(marks()).getAllByRole('listitem'), 1));
    act(() => viewer.props?.onSelect?.(null));
    expect(viewer.props?.selected).toBeNull();
  });

  it('SV-21 Reject and Restore send the review edits', async () => {
    const rejected = derive('door', {
      marks: [nth(doorMarks, 0), markAt(1, { state: 'rejected', n: null })],
    });
    const api = show('q=door', { [PATH.edit]: takeoff });
    await ready();
    fireEvent.click(nth(within(marks()).getAllByRole('button', { name: 'Reject' }), 1));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual(reviewRequests[0]);
    cleanup();
    const api2 = show('q=door', { [PATH.takeoff]: rejected, [PATH.edit]: takeoff });
    await ready();
    fireEvent.click(within(marks()).getByRole('button', { name: 'Restore' }));
    await waitFor(() => {
      expect(posted(api2, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api2, PATH.edit), 0).body).toEqual(reviewRequests[1]);
  });

  it('SV-22 area and added/excluded actions', async () => {
    const api = show('q=' + encodeURIComponent('area:room|indoor'), { [PATH.edit]: takeoff });
    await ready();
    fireEvent.click(nth(within(marks()).getAllByRole('button', { name: 'Leave out' }), 0));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual({
      quantity: 'area:room|indoor',
      action: 'reject',
      mark: 'm1',
    });
    cleanup();
    const odd = derive('door', {
      marks: [
        markAt(0, { id: 'a1', state: 'added', n: 3, label: null }),
        markAt(1, { id: 'x1', state: 'excluded', n: null, reason: 'open doorway' }),
      ],
    });
    const api2 = show('q=door', { [PATH.takeoff]: odd, [PATH.edit]: odd });
    await ready();
    fireEvent.click(within(marks()).getByRole('button', { name: 'Remove' }));
    await waitFor(() => {
      expect(posted(api2, PATH.edit)).toHaveLength(1);
    });
    fireEvent.click(within(marks()).getByRole('button', { name: 'Count in' }));
    await waitFor(() => {
      expect(posted(api2, PATH.edit)).toHaveLength(2);
    });
    expect(posted(api2, PATH.edit).map((c) => c.body)).toEqual([
      { quantity: 'door', action: 'reject', mark: 'a1' },
      { quantity: 'door', action: 'restore', mark: 'x1' },
    ]);
  });

  it('SV-23 an area with a mark of unknown value says leaving out does not recount', async () => {
    const indoor = rowOf(takeoff, 'area:room|indoor');
    show('q=' + encodeURIComponent(indoor.key), {
      [PATH.takeoff]: derive(indoor.key, {
        marks: [{ ...nth(indoor.marks, 0), value: null }, nth(indoor.marks, 1)],
      }),
    });
    await ready();
    expect(detail().textContent).toContain(
      "A room's area is unknown, so leaving rooms out does not change the total; settle a value instead.",
    );
  });

  it('SV-24 unlocated goes to the viewer and adds a line under the marks', async () => {
    show('q=door', { [PATH.takeoff]: derive('door', { unlocated: { door: 1 } }) });
    await ready();
    expect(viewer.props?.unlocated).toEqual({ door: 1 });
    expect(detail().textContent).toContain('+ 1 door counted with no mark');
  });
});

describe('edits', () => {
  const edited = derive('door', {
    value: 1,
    status: 'edited',
    marks: [nth(doorMarks, 0), markAt(1, { state: 'rejected', n: null })],
  });

  it('SV-25 a successful edit replaces the takeoff, keeps the selection and reloads the side panel', async () => {
    const api = show('q=door', { [PATH.edit]: edited });
    await ready();
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 1));
    await waitFor(() => {
      expect(screen.getByRole('row', { name: /door count/ }).textContent).toContain(
        'Changed in review',
      );
    });
    expect(within(detail()).getByRole('heading').textContent).toContain('door count');
    expect(within(detail()).getByRole('button', { name: 'Restore' })).toBeTruthy();
    await waitFor(() => {
      expect(api.calls.filter((c) => c.url.endsWith('/review') && c.method === 'GET')).toHaveLength(
        2,
      );
    });
  });

  it('SV-26 while saving, "Saving…" shows and the controls are disabled', async () => {
    show('q=door', { [PATH.edit]: never() });
    await ready();
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 0));
    expect(await screen.findByText('Saving…')).toBeTruthy();
    for (const b of within(detail()).getAllByRole('button'))
      expect(b).toHaveProperty('disabled', true);
  });

  it('SV-27 a refused edit shows detail and code and keeps the takeoff', async () => {
    let n = 0;
    show('q=door', {
      [PATH.edit]: () =>
        ++n === 1
          ? reply(409, { ...errorBody, detail: 'door is signed off', code: 'not-allowed' })
          : takeoff,
    });
    await ready();
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 0));
    const alert = await within(detail()).findByRole('alert');
    expect(alert.textContent).toContain('door is signed off');
    expect(alert.textContent).toContain('not-allowed');
    expect(screen.getByRole('row', { name: /door count/ }).textContent).toContain('One method');
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 0));
    await waitFor(() => {
      expect(within(detail()).queryByRole('alert')).toBeNull();
    });
  });

  it('SV-28 Add a missed one on counts only; a pick sends add and ends add mode', async () => {
    const api = show('', { [PATH.edit]: takeoff });
    await ready();
    expect(within(detail()).queryByRole('button', { name: 'Add a missed one' })).toBeNull();
    pick('door count');
    expect(viewer.props?.onPick).toBeUndefined();
    fireEvent.click(within(detail()).getByRole('button', { name: 'Add a missed one' }));
    expect(
      within(detail()).getByRole('button', {
        name: 'Click the missed item on the drawing… (Esc to cancel)',
      }),
    ).toBeTruthy();
    act(() => viewer.props?.onPick?.(1, [0.2, 0.5, 0.23, 0.53]));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual(reviewRequests[2]);
    await waitFor(() => {
      expect(viewer.props?.onPick).toBeUndefined();
    });
  });

  it('SV-29 Escape or the button again leaves add mode without a request', async () => {
    const api = show('q=door');
    await ready();
    const add = () =>
      within(detail()).getAllByRole('button', { name: /Add a missed one|Click the missed/ });
    fireEvent.click(nth(add(), 0));
    expect(viewer.props?.onPick).toBeDefined();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(viewer.props?.onPick).toBeUndefined();
    fireEvent.click(nth(add(), 0));
    fireEvent.click(nth(add(), 0));
    expect(viewer.props?.onPick).toBeUndefined();
    expect(posted(api, PATH.edit)).toHaveLength(0);
  });

  it('SV-30 Keep sends settle with that conflict value', async () => {
    const api = show('', { [PATH.edit]: takeoff });
    await ready();
    fireEvent.click(
      screen.getByRole('button', { name: `Keep B: 30.00 m² (${methodName('printed_label')})` }),
    );
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual({
      quantity: CONFLICT,
      action: 'settle',
      value: 30,
    });
    expect(
      screen.getByRole('button', { name: `Keep A: 22.40 m² (${methodName('polygon_x_scale')})` }),
    ).toBeTruthy();
  });

  it('SV-31 the Settle field sends the typed number and refuses bad input', async () => {
    const api = show('q=door', { [PATH.edit]: takeoff });
    await ready();
    const field = within(detail()).getByLabelText('Settle at');
    const button = within(detail()).getByRole('button', { name: 'Settle' });
    expect(button).toHaveProperty('disabled', true);
    fireEvent.change(field, { target: { value: '-1' } });
    expect(button).toHaveProperty('disabled', true);
    fireEvent.change(field, { target: { value: '3' } });
    fireEvent.click(button);
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual(reviewRequests[3]);
  });

  it('SV-32 a settled value shows with its time', async () => {
    show('', {
      [PATH.takeoff]: derive(CONFLICT, { settled: { value: 22.401, at: '2026-11-14T01:30:00Z' } }),
    });
    await ready();
    expect(detail().textContent).toContain(
      'Settled at 22.40 m² (2026-11-14 01:30 UTC). A mark edit clears it.',
    );
  });

  it('SV-33 Reset this quantity shows on an edited row and sends reset', async () => {
    show('q=door');
    await ready();
    expect(within(detail()).queryByRole('button', { name: 'Reset this quantity' })).toBeNull();
    cleanup();
    const api = show('q=door', { [PATH.takeoff]: edited, [PATH.edit]: takeoff });
    await ready();
    fireEvent.click(within(detail()).getByRole('button', { name: 'Reset this quantity' }));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual(reviewRequests[4]);
  });

  it('SV-34 Reset all edits asks first', async () => {
    const confirm = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    const api = show('', { [PATH.edit]: takeoff });
    await ready();
    const button = screen.getByRole('button', { name: 'Reset all edits' });
    fireEvent.click(button);
    expect(posted(api, PATH.edit)).toHaveLength(0);
    fireEvent.click(button);
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.edit), 0).body).toEqual(reviewRequests[5]);
    confirm.mockRestore();
  });
});

describe('sign-off', () => {
  it('SV-35 "Signing as" is required, limited, saved and survives a broken localStorage', async () => {
    localStorage.setItem('countersign.surveyorName', 'Bea');
    show('q=door', { [PATH.sign]: takeoff });
    await ready();
    const name = within(detail()).getByLabelText('Signing as');
    expect(name).toHaveProperty('value', 'Bea');
    expect(name).toHaveProperty('maxLength', 100);
    const sign = within(detail()).getByRole('button', { name: 'Sign off 2' });
    fireEvent.change(name, { target: { value: '   ' } });
    expect(sign).toHaveProperty('disabled', true);
    fireEvent.change(name, { target: { value: '  Ana ' } });
    fireEvent.click(sign);
    await waitFor(() => {
      expect(localStorage.getItem('countersign.surveyorName')).toBe('Ana');
    });
    cleanup();
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    show('q=door');
    await ready();
    expect(within(detail()).getByLabelText('Signing as')).toHaveProperty('value', '');
    get.mockRestore();
  });

  it('SV-36 Sign off sends the sign-off request', async () => {
    const api = show('q=door', { [PATH.sign]: signedDoor });
    await ready();
    fireEvent.change(within(detail()).getByLabelText('Signing as'), { target: { value: 'Ana' } });
    fireEvent.click(within(detail()).getByRole('button', { name: 'Sign off 2' }));
    await waitFor(() => {
      expect(posted(api, PATH.sign)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.sign), 0).body).toEqual(signoffRequest);
  });

  it('SV-37 no sign-off while a person must settle; allowed when a rule decides', async () => {
    localStorage.setItem('countersign.surveyorName', 'Ana');
    show('', { [PATH.takeoff]: needsPerson });
    await ready();
    expect(within(detail()).getByRole('button', { name: /^Sign off/ })).toHaveProperty(
      'disabled',
      true,
    );
    expect(detail().textContent).toContain('Settle a value before signing off.');
    cleanup();
    show();
    await ready();
    expect(within(detail()).getByRole('button', { name: 'Sign off 30.00 m²' })).toHaveProperty(
      'disabled',
      false,
    );
  });

  it('SV-38 a signed row locks its edits and offers Undo sign-off', async () => {
    localStorage.setItem('countersign.surveyorName', 'Ana');
    const api = show('q=door', { [PATH.takeoff]: signedDoor, [PATH.sign]: takeoff });
    await ready();
    const d = detail();
    expect(d.textContent).toContain(
      'Signed off by Ana, 2026-11-14 01:40 UTC: 2. Engineers see this value as verified.',
    );
    expect(d.textContent).toContain('Undo the sign-off to edit.');
    for (const name of ['Reject', 'Add a missed one', 'Settle']) {
      for (const b of within(d).getAllByRole('button', { name }))
        expect(b).toHaveProperty('disabled', true);
    }
    expect(within(d).queryByRole('button', { name: 'Reset this quantity' })).toBeNull();
    fireEvent.click(within(d).getByRole('button', { name: 'Undo sign-off' }));
    await waitFor(() => {
      expect(posted(api, PATH.sign)).toHaveLength(1);
    });
    expect(nth(posted(api, PATH.sign), 0).body).toEqual({
      quantity: 'door',
      by: 'Ana',
      undo: true,
    });
  });
});

describe('zeros, export', () => {
  it('SV-39 zeros reloads and travels with every later request', async () => {
    localStorage.setItem('countersign.surveyorName', 'Ana');
    const api = show('q=door', { [PATH.edit]: takeoff, [PATH.sign]: takeoff });
    await ready();
    fireEvent.click(screen.getByLabelText('Show rows with value 0'));
    await waitFor(() => {
      expect(
        api.calls.some((c) => c.url === `/api/drawings/${did}/takeoff?zeros=true&project=${pid}`),
      ).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Export CSV' }).getAttribute('href')).toContain(
        'zeros=true',
      );
    });
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 0));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    fireEvent.click(within(detail()).getByRole('button', { name: 'Sign off 2' }));
    await waitFor(() => {
      expect(posted(api, PATH.sign)).toHaveLength(1);
    });
    for (const c of api.calls.filter((x) => x.method === 'POST'))
      expect(c.url).toContain('?zeros=true');
  });

  it('SV-40 Export CSV is a download link to the CSV', async () => {
    show();
    await ready();
    const link = screen.getByRole('link', { name: 'Export CSV' });
    expect(link.getAttribute('href')).toBe(`/api/drawings/${did}/takeoff.csv?project=${pid}`);
    expect(link.hasAttribute('download')).toBe(true);
  });
});

describe('states', () => {
  it('SV-44 an empty takeoff says nothing was counted and offers zeros only', async () => {
    const empty: Takeoff = { ...takeoff, quantities: [], review_queue: [] };
    show('', {
      [PATH.takeoff]: empty,
      [PATH.drawing]: { ...drawing, reader: { ...drawing.reader, extractor: 'hello' } },
    });
    expect(await screen.findByText('Nothing was counted on this drawing.')).toBeTruthy();
    expect(
      screen.getByText("This drawing's route has no reader in this build, so nothing was counted."),
    ).toBeTruthy();
    expect(screen.getByLabelText('Show rows with value 0')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Export CSV' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Sign off/ })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reset all edits' })).toBeNull();
  });

  it('SV-45 a 404 leads back to the projects; any other load error offers Retry', async () => {
    show('', { [PATH.takeoff]: reply(404, errorBody) });
    const notFound = await screen.findByRole('alert');
    expect(notFound.textContent).toContain('no drawing 0123456789abcdef');
    expect(notFound.textContent).toContain('code: not-found');
    expect(
      within(notFound).getByRole('link', { name: 'Back to projects' }).getAttribute('href'),
    ).toBe('#/');
    expect(within(notFound).queryByRole('button', { name: 'Retry' })).toBeNull();
    cleanup();
    let fail = true;
    const internal = { ...errorBody, detail: 'internal error', code: 'internal' };
    const api = show('', { [PATH.takeoff]: () => (fail ? reply(500, internal) : takeoff) });
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('internal error');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await ready();
    expect(api.calls.filter((c) => c.url.includes('/takeoff'))).toHaveLength(2);
  });
});

describe('QA round 1', () => {
  it('R1-4-2 both tables sit in the takeoff column under one sticky header, with no inner scroll box', async () => {
    show();
    await ready();
    const panel = screen.getByRole('region', { name: 'Takeoff' });
    for (const name of ['To review', 'All other quantities']) {
      expect(screen.getByRole('table', { name }).parentElement).toBe(panel);
    }
    const head = panel.querySelector('header.sv-panel-head');
    expect(head?.textContent).toContain(`Takeoff: ${drawing.file}`);
    expect(head?.textContent).toContain('0 of 3 quantities signed off');
    expect(head?.querySelector('a[download]')?.textContent).toBe('Export CSV');
    const css = readFileSync('src/surveyor/surveyor.css', 'utf8'); // vitest runs in frontend/;
    // the 40vh box held both tables and showed one row of 61; the column scrolls instead
    expect(css).not.toMatch(/40vh/);
    expect(css).toMatch(/\.sv-panel-head\s*\{[^}]*position:\s*sticky/);
    expect(css).toMatch(/\.sv-work \.sv-panel\s*\{[^}]*overflow-y:\s*auto/);
  });
});

describe('QA round 1, project scope', () => {
  it('R1-PS-1 the drawing is read as this project uploaded it (?project=)', async () => {
    const api = show();
    await ready();
    expect(
      api.calls.filter((c) => c.url.startsWith(`/api/drawings/${did}?`)).map((c) => c.url),
    ).toEqual([`/api/drawings/${did}?project=${pid}`]);
  });

  it("R1-PS-2 the title and the viewer use the project's name of the drawing, not the takeoff's", async () => {
    show('', { [PATH.drawing]: { ...drawing, file: 'plans/kitchen-b.pdf' } });
    await ready();
    expect(screen.getByRole('heading', { name: 'Takeoff: plans/kitchen-b.pdf' })).toBeTruthy();
    expect(screen.queryByText(`Takeoff: ${takeoff.file}`)).toBeNull();
    expect(viewer.props?.file).toBe('plans/kitchen-b.pdf');
  });
  it('R1-PS-3 takeoff, review, sign-off and the CSV link carry project=<pid>', async () => {
    localStorage.setItem('countersign.surveyorName', 'Ana');
    const api = show('q=door', { [PATH.edit]: takeoff, [PATH.sign]: takeoff });
    await ready();
    fireEvent.click(nth(within(detail()).getAllByRole('button', { name: 'Reject' }), 0));
    await waitFor(() => {
      expect(posted(api, PATH.edit)).toHaveLength(1);
    });
    fireEvent.click(within(detail()).getByRole('button', { name: 'Sign off 2' }));
    await waitFor(() => {
      expect(posted(api, PATH.sign)).toHaveLength(1);
    });
    fireEvent.click(screen.getByLabelText('Show rows with value 0'));
    await waitFor(() => {
      expect(api.calls.filter((c) => c.url.includes('/takeoff?'))).toHaveLength(2);
    });
    const scoped = api.calls.filter(
      (c) => /\/(takeoff|review|signoff)(\?|$)/.test(c.url) && c.url.includes(`/drawings/${did}/`),
    );
    expect(scoped.map((c) => `${c.method} ${c.url.split('?')[0] ?? ''}`)).toEqual([
      `GET /api/drawings/${did}/takeoff`,
      `POST /api/drawings/${did}/review`,
      `POST /api/drawings/${did}/signoff`,
      `GET /api/drawings/${did}/takeoff`,
    ]);
    for (const c of scoped)
      expect(new URLSearchParams(c.url.split('?')[1]).get('project')).toBe(pid);
    const csv = screen.getByRole('link', { name: 'Export CSV' }).getAttribute('href') ?? '';
    expect(csv.split('?')[0]).toBe(`/api/drawings/${did}/takeoff.csv`);
    expect(new URLSearchParams(csv.split('?')[1]).get('project')).toBe(pid);
    expect(new URLSearchParams(csv.split('?')[1]).get('zeros')).toBe('true');
  });
});

describe('QA round 3', () => {
  it('R3-methods measuring methods show as methodName(), never as raw ids', async () => {
    show();
    await ready();
    const row = screen.getByRole('row', { name: /1\.01/ }).textContent;
    const text = detail().textContent;
    for (const id of ['polygon_x_scale', 'printed_label']) {
      expect(methodName(id)).not.toBe(id);
      expect(row).toContain(methodName(id));
      expect(text).toContain(methodName(id));
      expect(row).not.toContain(id);
      expect(text).not.toContain(id);
    }
    expect(
      within(detail()).getByRole('button', {
        name: `Keep A: 22.40 m² (${methodName('polygon_x_scale')})`,
      }),
    ).toBeTruthy();
  });
});
