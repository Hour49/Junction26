// conflicts.md: the conflicts list the finished ingest views embed (demo parity CF-35..44) and its cards.
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { methodName, type ConflictEntry, type ProjectReview } from '../api';
import {
  drawing,
  error as errorBody,
  project,
  projectReview,
  projectReviewResolved,
  resolving,
} from '../api/fixtures';
import { mockApi, reply } from '../test/mockApi';
import type { SourceFigureProps } from '../viewer/SourceFigure';
import { ProjectReviewSide } from './ProjectReviewSide';
import { ConflictsList } from './ConflictsScreen';
import { stubResizeObserver } from '../test/resizeObserver';
import { REVIEW_TIPS } from '../shell/tips-review';

// The source figure is fe-viewer's; here a double recording its props and counting its mounts.
const fig = vi.hoisted(() => ({ props: [] as SourceFigureProps[], mounts: 0 }));
vi.mock('../viewer/SourceFigure', () => ({
  SourceFigure: (props: SourceFigureProps) => {
    useState(() => (fig.mounts += 1));
    fig.props.push(props);
    return <div data-testid="figure" />;
  },
}));

const pid = project.id;
const base = projectReview.conflicts[0] as ConflictEntry;
const did = base.drawing_id;
const QTY = base.quantity; // area:room|name=1.01
const PATH = {
  project: `GET /api/projects/${pid}`,
  review: `GET /api/projects/${pid}/review`,
  drawing: `GET /api/drawings/${did}`,
  edit: `POST /api/drawings/${did}/review`,
};
const AT = '2026-11-14T01:30:00Z';
const needs: ConflictEntry = {
  ...base,
  quantity: 'door',
  label: 'door count',
  title: '', // an older backend: the card falls back to the sentence-case label
  needs_person: true,
  conflict: { ...base.conflict, resolution: null },
};
const yours: ConflictEntry = {
  ...base,
  quantity: 'window',
  label: 'window count',
  title: '',
  settled: { value: 22.401, at: AT },
  value: 22.401,
};
const withConflicts = (conflicts: ConflictEntry[]): ProjectReview => ({
  ...projectReview,
  conflicts,
});

function show(
  routes: Record<string, unknown> = {},
  query?: string,
  onCounts?: (c: { total: number; needsPerson: number }) => void,
) {
  const api = mockApi({
    [PATH.project]: project,
    [PATH.review]: projectReview,
    [PATH.drawing]: drawing,
    ...routes,
  });
  const view = render(
    <ConflictsList
      projectId={pid}
      query={query === undefined ? undefined : new URLSearchParams(query)}
      onCounts={onCounts}
    />,
  );
  return { api, ...view };
}
const ready = () => screen.findByRole('heading', { level: 2, name: /conflicts? found$/ });
const cards = () => screen.getAllByRole('article');
// the card's title: the server's `title` (#226, CF-49), else the label in sentence case (CF-46)
const title = (label: string) => label.charAt(0).toUpperCase() + label.slice(1);
const card = (label: string) =>
  screen.getByRole('article', { name: label === base.label ? base.title : title(label) });
const tile = (scope: HTMLElement, n: number) =>
  within(scope).getByRole('button', { name: new RegExp(`^Variant ${String(n)}:`) });
const pressed = (b: HTMLElement) => b.getAttribute('aria-pressed') === 'true';
const disabled = (b: HTMLElement) => (b as HTMLButtonElement).disabled;
const click = (el: HTMLElement) => {
  fireEvent.click(el);
};
const gets = (api: ReturnType<typeof mockApi>, url: string) =>
  api.calls.filter((c) => c.method === 'GET' && c.url === url).length;
const own = (scope: HTMLElement) => within(scope).queryByLabelText('Or type your own answer');

beforeEach(() => {
  fig.props = [];
  fig.mounts = 0;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ConflictsList', () => {
  it('CF-35 loads the review (and the project for names), renders the list heading, progress and card, reports counts', async () => {
    const counts = vi.fn();
    const { api, container } = show({}, undefined, counts);
    expect(screen.getByRole('status').textContent).toBe('Loading the conflicts…');
    expect(counts).not.toHaveBeenCalled();
    expect(container.querySelector('section#conflicts')).toBeTruthy(); // fe-scaffold's scroll target, also while loading
    expect((await ready()).textContent).toBe('1 conflict found');
    expect(screen.getByText('1 settled by a rule.')).toBeTruthy();
    expect(screen.getByText('1 of 1 settled')).toBeTruthy();
    expect(cards()).toHaveLength(1);
    // the project only for the drawings' plain names (#224), once
    expect(gets(api, `/api/projects/${pid}`)).toBe(1);
    const list = screen.getByRole('region', { name: 'Conflicts' });
    expect(list.id).toBe('conflicts');
    expect(list.tabIndex).toBe(-1); // fe-scaffold's "Show the conflict" moves focus here
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
    expect(screen.queryByText('Start a new chat')).toBeNull(); // the host's
    expect(counts).toHaveBeenLastCalledWith({ total: 1, needsPerson: 0 });
  });

  it('CF-35 onCounts follows a settle on a card that needed a person', async () => {
    const counts = vi.fn();
    let picked = false;
    show(
      {
        [PATH.edit]: () => {
          picked = true;
          return {};
        },
        [PATH.review]: () =>
          withConflicts([
            picked
              ? { ...needs, needs_person: false, settled: { value: 22.401, at: AT }, value: 22.401 }
              : needs,
          ]),
      },
      undefined,
      counts,
    );
    await ready();
    expect(counts).toHaveBeenLastCalledWith({ total: 1, needsPerson: 1 });
    click(tile(card(needs.label), 1));
    await waitFor(() => {
      expect(counts).toHaveBeenLastCalledWith({ total: 1, needsPerson: 0 });
    });
  });

  it('CF-36 a review error stays inside the list; Retry re-sends the GET', async () => {
    let fail = true;
    const { api } = show({
      [PATH.review]: () => (fail ? reply(500, { ...errorBody, detail: 'boom' }) : projectReview),
    });
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('boom');
    expect(alert.closest('section#conflicts')).toBeTruthy();
    fail = false;
    click(within(alert).getByRole('button', { name: 'Retry' }));
    await ready();
    expect(gets(api, `/api/projects/${pid}/review`)).toBe(2);
  });

  it('CF-37 rule-settled cards first, then the ones without a rule; settling keeps the order', async () => {
    const r1 = { ...base, quantity: 'r1', label: 'r1', title: '' };
    const r2 = { ...base, quantity: 'r2', label: 'r2', title: '' };
    const p = { ...needs, quantity: 'p', label: 'p' };
    const s = {
      ...needs,
      quantity: 's',
      label: 's',
      needs_person: false,
      settled: { value: 22.401, at: AT },
      value: 22.401,
    };
    let picked = false;
    show({
      [PATH.edit]: () => {
        picked = true;
        return {};
      },
      [PATH.review]: () =>
        withConflicts([
          picked ? { ...p, needs_person: false, settled: { value: 30, at: AT }, value: 30 } : p,
          r1,
          s,
          r2,
        ]),
    });
    await ready();
    const order = () =>
      cards().map((c) => c.getAttribute('aria-label') ?? c.querySelector('h2')?.textContent);
    expect(order()).toEqual(['R1', 'R2', 'P', 'S']);
    expect(card('p').textContent).toContain('Conflict 3 of 4 · needs you');
    click(tile(card('p'), 2));
    await waitFor(() => {
      expect(within(card('p')).getByText('Your choice')).toBeTruthy();
    });
    expect(order()).toEqual(['R1', 'R2', 'P', 'S']);
  });

  it('CF-3 three conflicts: counts, sub line, progress', async () => {
    const { container } = show({ [PATH.review]: withConflicts([needs, base, yours]) });
    expect((await ready()).textContent).toBe('3 conflicts found');
    expect(screen.getByText('1 settled by a rule. 1 settled by you. 1 needs you.')).toBeTruthy();
    expect(screen.getByText('2 of 3 settled')).toBeTruthy();
    expect(container.querySelectorAll('.cf-seg')).toHaveLength(3);
    expect(container.querySelectorAll('.cf-seg.cf-on')).toHaveLength(2);
    expect(cards()).toHaveLength(3);
  });

  it('CF-4b nothing measured (QA R2-E1): no agree line', async () => {
    const review = {
      ...withConflicts([]),
      drawings: projectReview.drawings.map((d) => ({ ...d, quantities: 0 })),
    };
    show({ [PATH.review]: review });
    expect((await ready()).textContent).toBe('No conflicts found');
    expect(
      screen.getByText('Nothing was measured on these drawings, so there was nothing to compare.'),
    ).toBeTruthy();
    expect(screen.queryByText('Both methods agree wherever two of them measured.')).toBeNull();
  });

  it('CF-4 no conflicts: agree line, no segments, no cards', async () => {
    const counts = vi.fn();
    const { container } = show({ [PATH.review]: withConflicts([]) }, undefined, counts);
    expect((await ready()).textContent).toBe('No conflicts found');
    expect(screen.getByText('Both methods agree wherever two of them measured.')).toBeTruthy();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(container.querySelector('.cf-segs')).toBeNull();
    expect(counts).toHaveBeenLastCalledWith({ total: 0, needsPerson: 0 });
  });

  it('CF-5 / CF-40 a rule card shows its kicker, label, file and numbered variant tiles', async () => {
    show();
    await ready();
    const c = card(base.label);
    expect(c.textContent).toContain('Conflict 1 of 1 · settled by a rule');
    const a = tile(c, 1);
    expect(a.textContent).toContain('Variant 1');
    expect(a.textContent).toContain('22.40 m²');
    expect(a.textContent).toContain(`${methodName('polygon_x_scale')}, page 1`);
    expect(pressed(a)).toBe(false);
    const b = tile(c, 2);
    expect(b.textContent).toContain("Variant 2 · the rule's choice");
    expect(b.textContent).toContain('30.00 m²');
    expect(pressed(b)).toBe(true);
    expect(b.getAttribute('aria-label')).toBe(
      `Variant 2: 30.00 m², ${methodName('printed_label')}, page 1, the rule's choice, in use`,
    );
    expect(within(c).getByText('Settled by rule')).toBeTruthy();
    expect(within(c).getByText(/^Why the rule chose variant 2$/)).toBeTruthy();
  });

  it('CF-6 Modify enables the tiles, Cancel restores them, no request', async () => {
    const { api } = show();
    await ready();
    const c = card(base.label);
    expect(disabled(tile(c, 1))).toBe(true);
    expect(own(c)).toBeNull();
    click(within(c).getByRole('button', { name: 'Modify' }));
    expect(disabled(tile(c, 1))).toBe(false);
    expect(within(c).getByText('Choosing')).toBeTruthy();
    click(within(c).getByRole('button', { name: 'Cancel' }));
    expect(disabled(tile(c, 1))).toBe(true);
    expect(within(c).getByRole('button', { name: 'Modify' })).toBeTruthy();
    expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(0);
  });

  it('CF-7 tapping a tile settles it, shows Saving…, then reloads the review', async () => {
    let answer!: (v: unknown) => void;
    let settled = false;
    const { api } = show({
      [PATH.edit]: () =>
        new Promise((r) => {
          answer = r;
        }),
      [PATH.review]: () =>
        settled
          ? withConflicts([{ ...base, settled: { value: 22.401, at: AT }, value: 22.401 }])
          : projectReview,
    });
    await ready();
    const c = card(base.label);
    click(within(c).getByRole('button', { name: 'Modify' }));
    click(tile(c, 1));
    expect(within(c).getByText('Saving…')).toBeTruthy();
    const post = api.calls.find((x) => x.method === 'POST');
    expect(post?.url).toBe(`/api/drawings/${did}/review?project=${pid}`);
    expect(post?.body).toEqual({ quantity: QTY, action: 'settle', value: 22.401 });
    settled = true;
    await act(async () => {
      answer({});
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(within(card(base.label)).getByText('Your choice')).toBeTruthy();
    });
    expect(gets(api, `/api/projects/${pid}/review`)).toBe(2);
  });

  it('CF-25 / CF-39 Why stays open and the figure is not remounted after a settle reloads the review', async () => {
    let settled = false;
    show({
      [PATH.edit]: () => {
        settled = true;
        return {};
      },
      [PATH.review]: () =>
        settled
          ? withConflicts([{ ...base, settled: { value: 22.401, at: AT }, value: 22.401 }])
          : projectReview,
    });
    await ready();
    const c = card(base.label);
    await within(c).findByTestId('figure');
    const why = within(c).getByText(/^Why /).closest('details') as HTMLDetailsElement;
    why.open = true;
    click(within(c).getByRole('button', { name: 'Modify' }));
    click(tile(c, 1));
    await waitFor(() => {
      expect(within(card(base.label)).getByText('Your choice')).toBeTruthy();
    });
    const after = card(base.label);
    expect((within(after).getByText(/^Why /).closest('details') as HTMLDetailsElement).open).toBe(
      true,
    );
    expect(fig.mounts).toBe(1);
    expect(within(after).getByRole('button', { name: 'Modify' })).toBeTruthy();
    expect(disabled(tile(after, 1))).toBe(true);
  });

  it('CF-8 a settled card shows Your choice, the kept tile and both buttons', async () => {
    show({
      [PATH.review]: withConflicts([
        { ...base, settled: { value: 22.401, at: AT }, value: 22.401 },
      ]),
    });
    await ready();
    const c = card(base.label);
    expect(within(c).getByText('Your choice')).toBeTruthy();
    expect(pressed(tile(c, 1))).toBe(true);
    expect(pressed(tile(c, 2))).toBe(false);
    expect(within(c).getByText("You kept variant 1, over the rule's choice.")).toBeTruthy();
    expect(within(c).getByRole('button', { name: 'Modify' })).toBeTruthy();
    expect(within(c).getByRole('button', { name: "Use the rule's value" })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Change' })).toBeNull();
  });

  it("CF-9 Use the rule's value sends unsettle at once and reloads the review", async () => {
    const confirm = vi.spyOn(window, 'confirm');
    const yoursNow = { ...base, settled: { value: 22.401, at: AT }, value: 22.401 };
    let sent = false;
    const { api } = show({
      [PATH.review]: () => withConflicts([sent ? base : yoursNow]),
      [PATH.edit]: () => {
        sent = true;
        return {};
      },
    });
    await ready();
    click(within(card(base.label)).getByRole('button', { name: "Use the rule's value" }));
    await waitFor(() => {
      expect(within(card(base.label)).getByText('Settled by rule')).toBeTruthy();
    });
    expect(confirm).not.toHaveBeenCalled();
    const posts = api.calls.filter((x) => x.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(posts[0]?.body).toEqual({ quantity: QTY, action: 'unsettle' });
  });

  it("CF-9b a 409 on Use the rule's value reads the signed-off sentence and keeps Your choice", async () => {
    show({
      [PATH.review]: withConflicts([
        { ...base, settled: { value: 22.401, at: AT }, value: 22.401 },
      ]),
      [PATH.edit]: reply(409, { ...errorBody, code: 'signed', detail: 'signed off' }),
    });
    await ready();
    const c = card(base.label);
    click(within(c).getByRole('button', { name: "Use the rule's value" }));
    const alert = await within(c).findByRole('alert');
    expect(alert.textContent).toBe(
      'This value is signed off. Undo the sign-off in the surveyor workspace first.',
    );
    expect(within(c).getByText('Your choice')).toBeTruthy();
  });

  it('CF-10 a card that needs a person: open tiles, none pressed, the typed box shown', async () => {
    show({ [PATH.review]: withConflicts([needs]) });
    await ready();
    const c = card(needs.label);
    expect(within(c).getByText('Needs you')).toBeTruthy();
    for (const n of [1, 2]) {
      expect(disabled(tile(c, n))).toBe(false);
      expect(pressed(tile(c, n))).toBe(false);
    }
    expect(within(c).getByText('Tap the right value.')).toBeTruthy();
    expect(own(c)).toBeTruthy();
    expect(within(c).getByText(/^Why no rule decides$/)).toBeTruthy();
  });

  it('CF-11 / CF-43 a settled value no tile has: none pressed, Your answer', async () => {
    show({
      [PATH.review]: withConflicts([{ ...base, settled: { value: 25.5, at: AT }, value: 25.5 }]),
    });
    await ready();
    const c = card(base.label);
    expect(pressed(tile(c, 1)) || pressed(tile(c, 2))).toBe(false);
    expect(within(c).getByText('Your answer: 25.50 m².')).toBeTruthy();
  });

  it('CF-12 / CF-38 each drawing is fetched once; the figure gets one place per value, minimized', async () => {
    const { api } = show({
      [PATH.review]: withConflicts([base, { ...base, quantity: 'x', label: 'x', title: '' }]),
    });
    await ready();
    await waitFor(() => {
      expect(screen.getAllByTestId('figure')).toHaveLength(2);
    });
    expect(gets(api, `/api/drawings/${did}?project=${pid}`)).toBe(1);
    const p = fig.props.at(-1);
    expect(p?.label).toBe('Source of conflict 2');
    expect(p?.defaultOpen).toBeFalsy();
    expect(p?.sources).toEqual([
      {
        name: 'Drawn plan 2',
        page: drawing.pages[0],
        // value_marks (#221), each mark labelled in plain words and tied to its variant
        places: [
          {
            label: `Variant 1: ${methodName('polygon_x_scale')}`,
            box: base.conflict.value_marks[0]?.[0]?.box,
          },
          {
            label: `Variant 2: ${methodName('printed_label')}`,
            box: base.conflict.value_marks[1]?.[0]?.box,
          },
        ],
      },
    ]);
    expect(screen.queryByText('Where each value was read')).toBeNull();
  });

  it('CF-38 a count lists each element; a value with no marks has no place; another page is legend-only', async () => {
    const mark = (label: string, page = 1) => ({
      page,
      box: [0.1, 0.1, 0.2, 0.2] as [number, number, number, number],
      label,
    });
    show({
      [PATH.review]: withConflicts([
        {
          ...base,
          conflict: { ...base.conflict, value_marks: [[mark('door'), mark('door', 2)], []] },
        },
      ]),
    });
    await ready();
    await screen.findByTestId('figure');
    expect(fig.props.at(-1)?.sources[0]?.places).toEqual([
      { label: 'Variant 1: door', box: [0.1, 0.1, 0.2, 0.2] },
      { label: 'Variant 1: door, on page 2', box: null },
    ]);
    cleanup();
    show({
      [PATH.review]: withConflicts([
        { ...base, conflict: { ...base.conflict, value_marks: [[], []] } },
      ]),
    });
    await ready();
    await screen.findByTestId('figure');
    expect(fig.props.at(-1)?.sources[0]?.places).toEqual([]);
  });

  it('CF-38 a backend without value_marks (before #221) shows the drawing without outlines, no crash', async () => {
    const older: Partial<typeof base.conflict> = { ...base.conflict };
    delete older.value_marks;
    show({ [PATH.review]: withConflicts([{ ...base, conflict: older as typeof base.conflict }]) });
    await ready();
    await screen.findByTestId('figure');
    expect(fig.props.at(-1)?.sources[0]?.places).toEqual([]);
    expect(fig.props.at(-1)?.sources[0]?.page).toEqual(drawing.pages[0]);
  });

  it('CF-13 a drawing error shows an error line with Retry inside that card only', async () => {
    let fail = true;
    const { api } = show({
      [PATH.drawing]: () => (fail ? reply(500, { ...errorBody, detail: 'boom' }) : drawing),
    });
    await ready();
    const c = card(base.label);
    const alert = await within(c).findByRole('alert');
    expect(alert.textContent).toContain('boom');
    expect(tile(c, 1)).toBeTruthy();
    fail = false;
    click(within(alert).getByRole('button', { name: 'Retry' }));
    await within(c).findByTestId('figure');
    expect(gets(api, `/api/drawings/${did}?project=${pid}`)).toBe(2);
  });

  it('CF-14 a 409 on settle reads the signed-off sentence and returns to choosing', async () => {
    show({ [PATH.edit]: reply(409, { ...errorBody, code: 'signed', detail: 'signed off' }) });
    await ready();
    const c = card(base.label);
    click(within(c).getByRole('button', { name: 'Modify' }));
    click(tile(c, 1));
    const alert = await within(c).findByRole('alert');
    expect(alert.textContent).toContain(
      'This value is signed off. Undo the sign-off in the surveyor workspace first.',
    );
    expect(within(c).getByRole('button', { name: 'Cancel' })).toBeTruthy();
    expect(disabled(tile(c, 1))).toBe(false);
  });

  it('CF-41 the typed answer: a number settles as a value, words go as a note (#226)', async () => {
    let body: unknown = null;
    const { api } = show({
      [PATH.edit]: (req: { body: unknown }) => {
        body = req.body;
        return {};
      },
      [PATH.review]: () =>
        withConflicts([
          body === null
            ? base
            : 'note' in (body as object)
              ? {
                  ...base,
                  settled: { value: 30, at: AT, note: 'room 1.01 is the kitchen' },
                  value: 30,
                }
              : { ...base, settled: { value: 25.5, at: AT }, value: 25.5 },
        ]),
    });
    await ready();
    const c = card(base.label);
    click(within(c).getByRole('button', { name: 'Modify' }));
    const box = own(c) as HTMLInputElement;
    expect(box.getAttribute('inputmode')).toBeNull(); // words too, not a number pad
    expect(box.maxLength).toBe(280);
    click(within(c).getByRole('button', { name: 'Use my answer' }));
    const alert = within(c).getByRole('alert');
    expect(alert.textContent).toBe('Type a number or a few words.');
    expect(box.getAttribute('aria-describedby')).toBe(alert.id);
    expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(0);
    fireEvent.change(box, { target: { value: ' 25,5 m² ' } });
    fireEvent.submit(box.closest('form') as HTMLFormElement);
    await waitFor(() => {
      expect(within(card(base.label)).getByText('Your answer: 25.50 m².')).toBeTruthy();
    });
    expect(body).toEqual({ quantity: QTY, action: 'settle', value: 25.5 });
    const c2 = card(base.label);
    click(within(c2).getByRole('button', { name: 'Modify' }));
    fireEvent.change(own(c2) as HTMLInputElement, {
      target: { value: 'room 1.01 is the kitchen' },
    });
    click(within(c2).getByRole('button', { name: 'Use my answer' }));
    await waitFor(() => {
      expect(
        within(card(base.label)).getByText('You answered: “room 1.01 is the kitchen”.'),
      ).toBeTruthy();
    });
    expect(body).toEqual({ quantity: QTY, action: 'settle', note: 'room 1.01 is the kitchen' });
  });

  it('CF-41 a count takes whole numbers only', async () => {
    const doors: ConflictEntry = {
      ...needs,
      conflict: {
        ...needs.conflict,
        values: needs.conflict.values.map((v, i) => ({
          ...v,
          unit: 'count' as const,
          value: 11 + 2 * i,
        })),
      },
    };
    const { api } = show({ [PATH.review]: withConflicts([doors]) });
    await ready();
    const c = card(needs.label);
    const box = own(c) as HTMLInputElement;
    fireEvent.change(box, { target: { value: '2.5' } });
    click(within(c).getByRole('button', { name: 'Use my answer' }));
    expect(within(c).getByRole('alert').textContent).toBe('Type a whole number, like 12.');
    expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(0);
  });

  it('CF-42 / CF-51 suggestions that restate a variant are not chips; one that adds something fills the box', async () => {
    const extra: ConflictEntry = {
      ...needs,
      suggestions: ['22.40 m²', '30 m²', 'Both are the same room'],
    };
    const { api, container } = show({ [PATH.review]: withConflicts([extra, base]) });
    await ready();
    // the fixture's suggestions are exactly its two values: no chips
    click(within(card(base.label)).getByRole('button', { name: 'Modify' }));
    expect(card(base.label).querySelector('.cf-chips')).toBeNull();
    const c = card(needs.label);
    const chips = [...c.querySelectorAll<HTMLButtonElement>('.cf-chips button')];
    expect(chips.map((b) => b.textContent)).toEqual(['Both are the same room']);
    click(chips[0] as HTMLElement);
    expect((own(c) as HTMLInputElement).value).toBe('Both are the same room');
    expect(document.activeElement).toBe(own(c));
    expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(0);
    expect(container.querySelectorAll('.cf-chips')).toHaveLength(1);
  });

  it("CF-49 / CF-50 the title and the why are the server's plain words; older entries fall back", async () => {
    show({ [PATH.review]: withConflicts([base, { ...needs, why: '' }]) });
    await ready();
    const c = card(base.label);
    expect(within(c).getByRole('heading', { level: 2 }).textContent).toBe(base.title);
    const why = within(c).getByText(/^Why /).closest('details') as HTMLElement;
    expect(why.textContent).toContain(base.why);
    expect(why.querySelector('ul')).toBeNull();
    const old = card(needs.label);
    expect(within(old).getByRole('heading', { level: 2 }).textContent).toBe('Door count');
    expect(
      within(old).getByText(/^Why /).closest('details')?.querySelector('ul, p')?.textContent,
    ).toBeTruthy();
  });

  it('CF-27 after a person picks a value on a card that needed one, the button is Modify', async () => {
    let picked = false;
    show({
      [PATH.edit]: () => {
        picked = true;
        return {};
      },
      [PATH.review]: () =>
        withConflicts([
          picked
            ? { ...needs, needs_person: false, settled: { value: 22.401, at: AT }, value: 22.401 }
            : needs,
        ]),
    });
    await ready();
    click(tile(card(needs.label), 1));
    await waitFor(() => {
      expect(within(card(needs.label)).getByText('Your choice')).toBeTruthy();
    });
    expect(within(card(needs.label)).getByRole('button', { name: 'Modify' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Change' })).toBeNull();
  });

  it('CF-48 the card names its drawing by the plain name (#224); a failed project GET falls back to the file name', async () => {
    show();
    await ready();
    const c = card(base.label);
    expect(c.querySelector('.cf-file')?.textContent).toBe('Drawn plan 2');
    expect(c.textContent).not.toContain(base.file);
    await within(c).findByTestId('figure');
    expect(fig.props.at(-1)?.sources[0]?.name).toBe('Drawn plan 2');
    cleanup();
    show({ [PATH.project]: reply(500, errorBody) });
    await ready();
    await waitFor(() => {
      expect(card(base.label).querySelector('.cf-file')?.textContent).toBe('flat-b.pdf');
    });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('CF-46 / CF-47 the title is in sentence case; the foot has Modify only, no workspace link', async () => {
    show();
    await ready();
    const c = card(base.label);
    expect(within(c).getByRole('heading', { level: 2 }).textContent).toBe(base.title);
    expect(within(c).queryAllByRole('link')).toHaveLength(0);
    const foot = c.querySelector('.cf-buttons') as HTMLElement;
    expect(
      within(foot)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Modify']);
    expect(within(foot).getByRole('button', { name: 'Modify' }).className).toContain('cf-soft');
  });

  it('CF-19 the side panel links to the project (the conflicts are on Ingest) when there are conflicts', async () => {
    mockApi({ [PATH.review]: projectReview });
    render(<ProjectReviewSide projectId={pid} drawingId={did} />);
    const link = await screen.findByRole('link', { name: 'Settle the conflicts' });
    expect(link.getAttribute('href')).toBe(`#/p/${pid}`);
    cleanup();
    mockApi({ [PATH.review]: withConflicts([]) });
    render(<ProjectReviewSide projectId={pid} drawingId={did} />);
    await screen.findByRole('list', { name: /Conflicts/ });
    expect(screen.queryByRole('link', { name: 'Settle the conflicts' })).toBeNull();
  });

  it('CF-20 none of the design mock values appear', async () => {
    show({ [PATH.review]: withConflicts([needs, base, yours]) });
    await ready();
    const text = document.body.textContent;
    for (const mock of [
      'harbour',
      'Beatrice',
      'IfcDoor',
      'Finland',
      'Germany',
      ' AI ',
      'AI decision',
    ])
      expect(text).not.toContain(mock);
  });

  it('CF-21 the pill is focusable and its tip is the shared Tip, its accessible description', async () => {
    stubResizeObserver();
    show();
    await ready();
    const pill = within(card(base.label)).getByText('Settled by rule');
    expect(pill.tabIndex).toBe(0);
    pill.focus();
    const tip = await screen.findByRole('tooltip');
    expect(tip.textContent).toBe(
      `A rule settled this: ${String(base.conflict.resolution?.rule)}. Modify it if you disagree.`,
    );
    expect(pill.getAttribute('aria-describedby')).toBe(tip.id);
  });

  it('TIP-6 the kicker says what a conflict is; a signed card says why its choices are locked', async () => {
    stubResizeObserver();
    const signed: ConflictEntry = { ...base, signed: { by: 'Ana', at: AT, value: 30 } };
    show({ [PATH.review]: withConflicts([signed]) });
    await ready();
    const c = card(base.label);
    expect(await tipOf(within(c).getByText(/^Conflict 1 of /))).toBe(REVIEW_TIPS.conflictKicker);
    const t = tile(c, 1);
    expect(disabled(t)).toBe(true);
    expect(await tipOf(t.parentElement as HTMLElement)).toBe(REVIEW_TIPS.choiceLocked);
  });

  it('CF-23 a real sign-off on the entry locks the card and names the signer', async () => {
    const signed: ConflictEntry = { ...base, signed: { by: 'Ana', at: AT, value: 30 } };
    show({ [PATH.review]: withConflicts([signed]) });
    await ready();
    const c = card(base.label);
    expect(within(c).getByText('Signed off by Ana')).toBeTruthy();
    expect(disabled(tile(c, 1))).toBe(true);
    expect(within(c).queryByRole('button', { name: 'Modify' })).toBeNull();
  });

  it('CF-24 a row value no tile has (a recount) presses no tile and reads In use', async () => {
    show({ [PATH.review]: withConflicts([{ ...base, value: 27.5 }]) });
    await ready();
    const c = card(base.label);
    expect(pressed(tile(c, 1)) || pressed(tile(c, 2))).toBe(false);
    expect(within(c).getByText('In use: 27.50 m².')).toBeTruthy();
  });

  it('CF-29 / CF-39 d + q bring that card into view, mark it, open its figure, focus its title', async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    show({}, `d=${did}&q=${encodeURIComponent(QTY)}`);
    await ready();
    const c = card(base.label);
    await waitFor(() => {
      expect(scroll.mock.contexts).toContain(c);
    });
    expect(c.getAttribute('aria-current')).toBe('true');
    await within(c).findByTestId('figure');
    expect(fig.props.at(-1)?.defaultOpen).toBe(true);
    expect(document.activeElement).toBe(within(c).getByRole('heading', { level: 2 }));
    cleanup();
    scroll.mockClear();
    show({}, `d=${did}&q=nope`);
    await ready();
    expect(card(base.label).getAttribute('aria-current')).toBeNull();
    expect(scroll).not.toHaveBeenCalled();
  });
});

// resolver.md RS-10..15 (#252): a model's pick on a conflict no rule decides.
describe('ConflictsList with a resolver', () => {
  const picked = projectReviewResolved.conflicts[0] as ConflictEntry;
  const cannot = resolving.review.conflicts[0] as ConflictEntry;
  const pickedCard = () => screen.getByRole('article', { name: picked.title });

  it('RS-10 a pick in use: Picked by Carbon (model in the tooltip), the reason, You can change it, its tile in use', async () => {
    show({ [PATH.review]: projectReviewResolved });
    await ready();
    const c = pickedCard();
    expect(within(c).getAllByText('Picked by Carbon').length).toBeGreaterThan(0);
    expect(within(c).getByTitle('gemini-4-carbon').textContent).toBe('Picked by Carbon');
    expect(within(c).getByText(picked.resolved?.reason ?? '-')).toBeTruthy();
    expect(within(c).getByText('You can change it.')).toBeTruthy();
    expect(within(c).getByRole('button', { name: 'Modify' })).toBeTruthy();
    expect(pressed(tile(c, 1))).toBe(true);
    expect(pressed(tile(c, 2))).toBe(false);
    expect(c.textContent).not.toMatch(/settled by a rule|Settled by rule|\bAI\b|gemini/i);
  });

  it("RS-11 the pick's marks are drawn on the card's plan beside value_marks, with their labels", async () => {
    show({ [PATH.review]: projectReviewResolved });
    await ready();
    await screen.findByTestId('figure');
    const places = fig.props.at(-1)?.sources[0]?.places ?? [];
    const marks = picked.resolved?.marks ?? [];
    expect(places).toHaveLength(2 + marks.length);
    expect(places.slice(2)).toEqual(
      marks.map((m) => ({ label: `Picked by Carbon: ${m.label}`, box: m.box })),
    );
  });

  it('RS-12 cannot_tell: Needs you, Carbon could not tell and the reason, no tile in use', async () => {
    show({ [PATH.review]: resolving.review });
    await ready();
    const c = screen.getByRole('article', { name: cannot.title });
    expect(within(c).getByText('Needs you')).toBeTruthy();
    expect(within(c).getByTitle('gemini-4-carbon').textContent).toBe('Carbon could not tell');
    expect(within(c).getByText(cannot.resolved?.reason ?? '-')).toBeTruthy();
    expect(pressed(tile(c, 1)) || pressed(tile(c, 2))).toBe(false);
    expect(screen.getByText('1 needs you.')).toBeTruthy();
  });

  it('RS-13 the list line counts the pick apart and as settled', async () => {
    show({ [PATH.review]: projectReviewResolved });
    await ready();
    expect(screen.getByText('1 picked by Carbon, check them.')).toBeTruthy();
    expect(screen.getByText('1 of 1 settled')).toBeTruthy();
  });

  it("RS-14 settling a pick posts the settle and shows settled by you; Use Carbon's pick unsettles and the pick is back", async () => {
    let state: 'picked' | 'yours' = 'picked';
    const yoursNow = { ...picked, settled: { value: 30, at: AT }, value: 30 };
    const { api } = show({
      [PATH.review]: () => withConflicts([state === 'picked' ? picked : yoursNow]),
      [PATH.edit]: ({ body }: { body: { action: string } }) => {
        state = body.action === 'settle' ? 'yours' : 'picked';
        return {};
      },
    });
    await ready();
    click(within(pickedCard()).getByRole('button', { name: 'Modify' }));
    click(tile(pickedCard(), 2));
    await waitFor(() => {
      expect(within(pickedCard()).getByText('Your choice')).toBeTruthy();
    });
    expect(within(pickedCard()).getByText(/settled by you/)).toBeTruthy();
    click(within(pickedCard()).getByRole('button', { name: "Use Carbon's pick" }));
    await waitFor(() => {
      expect(within(pickedCard()).getByText('You can change it.')).toBeTruthy();
    });
    expect(api.calls.filter((x) => x.method === 'POST').map((x) => x.body)).toEqual([
      { quantity: QTY, action: 'settle', value: 30 },
      { quantity: QTY, action: 'unsettle' },
    ]);
  });

  it("RS-15 the card's why stops after 'No rule decides between them.'", async () => {
    show({ [PATH.review]: projectReviewResolved });
    await ready();
    const why = within(pickedCard()).getByText(/^Why /).closest('details') as HTMLElement;
    expect(why.textContent).toContain('No rule decides between them.');
    expect(why.textContent).not.toMatch(/model|carbon:|gemini/);
  });
});

/** ui-tooltips: the text of the shared Tip on (or around) this element, opened by keyboard focus. */
async function tipOf(el: HTMLElement) {
  const trigger = el.closest<HTMLElement>('[data-slot="tooltip-trigger"]') ?? el;
  trigger.focus();
  const text = (await screen.findByRole('tooltip')).textContent;
  fireEvent.keyDown(trigger, { key: 'Escape' });
  trigger.blur();
  return text;
}
