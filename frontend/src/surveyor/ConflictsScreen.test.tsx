import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { methodName, type ConflictEntry, type ProjectReview } from '../api';
import {
  drawing,
  error as errorBody,
  project,
  projectFailed,
  projectReview,
  projectRunning,
} from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import type { PageViewerProps } from '../viewer/PageViewer';
import { ProjectReviewSide } from './ProjectReviewSide';
import { ConflictsScreen } from './ConflictsScreen';

// The viewer is a test double recording its props (as in SurveyorScreen.test.tsx).
const viewer = vi.hoisted(() => ({ props: [] as PageViewerProps[] }));
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: PageViewerProps) => {
    viewer.props.push(props);
    return <div data-testid="viewer" />;
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
  needs_person: true,
  conflict: { ...base.conflict, resolution: null },
};
const yours: ConflictEntry = {
  ...base,
  quantity: 'window',
  label: 'window count',
  settled: { value: 22.401, at: AT },
  value: 22.401,
};
const withConflicts = (conflicts: ConflictEntry[]): ProjectReview => ({
  ...projectReview,
  conflicts,
});

function show(routes: Record<string, unknown> = {}) {
  const api = mockApi({
    [PATH.project]: project,
    [PATH.review]: projectReview,
    [PATH.drawing]: drawing,
    ...routes,
  });
  const view = render(<ConflictsScreen projectId={pid} />);
  return { api, ...view };
}
const ready = () => screen.findByRole('heading', { level: 1 });
const cards = () => screen.getAllByRole('article');
const card = (label: string) => screen.getByRole('article', { name: label });
const tile = (scope: HTMLElement, l: string) =>
  within(scope).getByRole('button', { name: new RegExp(`^${l}\\b`) });
const pressed = (b: HTMLElement) => b.getAttribute('aria-pressed') === 'true';
const disabled = (b: HTMLElement) => (b as HTMLButtonElement).disabled;
const click = (el: HTMLElement) => {
  fireEvent.click(el);
};
const gets = (api: ReturnType<typeof mockApi>, url: string) =>
  api.calls.filter((c) => c.method === 'GET' && c.url === url).length;
const evidence = (scope: HTMLElement) => within(scope).getByText('Where each value was read');

beforeEach(() => {
  viewer.props = [];
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ConflictsScreen', () => {
  it('CF-1 loads the project and its review in parallel, Loading until both answer', async () => {
    const { api } = show({ [PATH.review]: never() });
    expect(screen.getByRole('status').textContent).toBe('Loading the conflicts…');
    await waitFor(() => {
      expect(api.calls.map((c) => c.url)).toEqual(
        expect.arrayContaining([`/api/projects/${pid}`, `/api/projects/${pid}/review`]),
      );
    });
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
  });

  it('CF-2 the heading for the fixture review', async () => {
    show();
    expect((await ready()).textContent).toBe('1 conflict found');
    expect(screen.getByText(`${project.name} · 5 drawings ready`)).toBeTruthy();
    expect(screen.getByText('1 settled by a rule.')).toBeTruthy();
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

  it('CF-4 no conflicts: agree line, no cards, workspace unlocked', async () => {
    show({ [PATH.review]: withConflicts([]) });
    expect((await ready()).textContent).toBe('No conflicts found');
    expect(screen.getByText('Both methods agree wherever two of them measured.')).toBeTruthy();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(screen.getByRole('link', { name: 'Open the workspace' })).toBeTruthy();
  });

  it('CF-5 a rule card shows its kicker, label, file and lettered tiles', async () => {
    show();
    await ready();
    const c = card(base.label);
    expect(c.textContent).toContain('Conflict 1 of 1 · settled by a rule');
    expect(c.textContent).toContain(base.file);
    const a = tile(c, 'A');
    expect(a.textContent).toContain('22.40 m²');
    expect(a.textContent).toContain(`${methodName('polygon_x_scale')}, page 1`);
    expect(pressed(a)).toBe(false);
    const b = tile(c, 'B');
    expect(b.textContent).toContain('30.00 m²');
    expect(b.textContent).toContain("· the rule's choice");
    expect(pressed(b)).toBe(true);
    expect(within(c).getByText('Settled by rule')).toBeTruthy();
  });

  it('CF-6 Modify enables the tiles, Cancel restores them, no request', async () => {
    const { api } = show();
    await ready();
    const c = card(base.label);
    expect(disabled(tile(c, 'A'))).toBe(true);
    click(within(c).getByRole('button', { name: 'Modify' }));
    expect(disabled(tile(c, 'A'))).toBe(false);
    expect(within(c).getByText('Choosing')).toBeTruthy();
    click(within(c).getByRole('button', { name: 'Cancel' }));
    expect(disabled(tile(c, 'A'))).toBe(true);
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
    click(tile(c, 'A'));
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

  it('CF-8 a settled card shows Your choice, the kept tile and both buttons', async () => {
    show({
      [PATH.review]: withConflicts([
        { ...base, settled: { value: 22.401, at: AT }, value: 22.401 },
      ]),
    });
    await ready();
    const c = card(base.label);
    expect(within(c).getByText('Your choice')).toBeTruthy();
    expect(pressed(tile(c, 'A'))).toBe(true);
    expect(pressed(tile(c, 'B'))).toBe(false);
    expect(within(c).getByText("You kept A, over the rule's choice.")).toBeTruthy();
    expect(within(c).getByRole('button', { name: 'Change' })).toBeTruthy();
    expect(within(c).getByRole('button', { name: "Use the rule's value" })).toBeTruthy();
  });

  it("CF-9 Use the rule's value asks first; yes sends reset, no sends nothing", async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { api } = show({
      [PATH.review]: withConflicts([
        { ...base, settled: { value: 22.401, at: AT }, value: 22.401 },
      ]),
      [PATH.edit]: {},
    });
    await ready();
    const use = () => {
      click(within(card(base.label)).getByRole('button', { name: "Use the rule's value" }));
    };
    use();
    expect(confirm).toHaveBeenCalledWith(
      `Use the rule's value? This also undoes every other edit and any sign-off of ${base.label} on ${base.file}.`,
    );
    expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(0);
    confirm.mockReturnValue(true);
    use();
    await waitFor(() => {
      expect(api.calls.filter((x) => x.method === 'POST')).toHaveLength(1);
    });
    const post = api.calls.find((x) => x.method === 'POST');
    expect(post?.url).toBe(`/api/drawings/${did}/review?project=${pid}`);
    expect(post?.body).toEqual({ quantity: QTY, action: 'reset' });
  });

  it('CF-10 a card that needs a person: open tiles, evidence open, workspace locked', async () => {
    show({ [PATH.review]: withConflicts([needs]) });
    await ready();
    const c = card(needs.label);
    expect(within(c).getByText('Needs you')).toBeTruthy();
    for (const l of ['A', 'B']) {
      expect(disabled(tile(c, l))).toBe(false);
      expect(pressed(tile(c, l))).toBe(false);
    }
    expect(within(c).getByText('Tap the right value.')).toBeTruthy();
    expect(c.querySelector('details.cf-evidence')?.hasAttribute('open')).toBe(true);
    const lock = screen.getByRole('button', { name: 'Open the workspace' });
    expect(disabled(lock)).toBe(true);
    const why = document.getElementById(lock.getAttribute('aria-describedby') ?? '');
    expect(why?.textContent).toBe('Settle the conflicts that need you first.');
    expect(screen.queryByRole('link', { name: 'Open the workspace' })).toBeNull();
  });

  it('CF-11 a settled value no tile has: none pressed, settled-elsewhere words', async () => {
    show({
      [PATH.review]: withConflicts([{ ...base, settled: { value: 25, at: AT }, value: 25 }]),
    });
    await ready();
    const c = card(base.label);
    expect(pressed(tile(c, 'A')) || pressed(tile(c, 'B'))).toBe(false);
    expect(
      within(c).getByText('You settled it at 25.00 m² in the surveyor workspace.'),
    ).toBeTruthy();
  });

  it('CF-12 the evidence fetches each drawing once and shows the viewer with the conflict', async () => {
    const { api } = show({
      [PATH.review]: withConflicts([base, { ...base, quantity: 'x', label: 'x' }]),
    });
    await ready();
    click(evidence(card(base.label)));
    click(evidence(card('x')));
    await waitFor(() => {
      expect(screen.getAllByTestId('viewer')).toHaveLength(2);
    });
    expect(gets(api, `/api/drawings/${did}?project=${pid}`)).toBe(1);
    const last = viewer.props.at(-1);
    expect(last?.marks).toEqual([]);
    expect(last?.conflict).toEqual(base.conflict);
    expect(last?.file).toBe(drawing.file);
    expect(last?.pages).toEqual(drawing.pages);
  });

  it('CF-13 a drawing error shows an error line with Retry inside that card only', async () => {
    let fail = true;
    const { api } = show({
      [PATH.drawing]: () => (fail ? reply(500, { ...errorBody, detail: 'boom' }) : drawing),
    });
    await ready();
    const c = card(base.label);
    click(evidence(c));
    const alert = await within(c).findByRole('alert');
    expect(alert.textContent).toContain('boom');
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
    fail = false;
    click(within(alert).getByRole('button', { name: 'Retry' }));
    await within(c).findByTestId('viewer');
    expect(gets(api, `/api/drawings/${did}?project=${pid}`)).toBe(2);
  });

  it('CF-14 a 409 on settle reads the signed-off sentence and returns to choosing', async () => {
    show({ [PATH.edit]: reply(409, { ...errorBody, code: 'signed', detail: 'signed off' }) });
    await ready();
    const c = card(base.label);
    click(within(c).getByRole('button', { name: 'Modify' }));
    click(tile(c, 'A'));
    const alert = await within(c).findByRole('alert');
    expect(alert.textContent).toContain(
      'This value is signed off. Undo the sign-off in the surveyor workspace first.',
    );
    expect(within(c).getByRole('link', { name: 'Open in the surveyor workspace' })).toBeTruthy();
    expect(within(c).getByRole('button', { name: 'Cancel' })).toBeTruthy();
    expect(disabled(tile(c, 'A'))).toBe(false);
  });

  it('CF-15 a 404 leads back to projects; a 500 retries both loads', async () => {
    show({ [PATH.project]: reply(404, { ...errorBody, code: 'not_found' }) });
    expect(
      (await screen.findByRole('link', { name: 'Back to projects' })).getAttribute('href'),
    ).toBe('#/');
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
    cleanup();
    let fail = true;
    const { api } = show({ [PATH.review]: () => (fail ? reply(500, errorBody) : projectReview) });
    const retry = await screen.findByRole('button', { name: 'Retry' });
    fail = false;
    click(retry);
    await ready();
    expect(gets(api, `/api/projects/${pid}`)).toBe(2);
    expect(gets(api, `/api/projects/${pid}/review`)).toBe(2);
  });

  it('CF-16 a running project says so and Check again reloads both', async () => {
    const { api } = show({ [PATH.project]: projectRunning });
    await ready();
    expect(
      screen.getByText('Still reading the drawings: these are the conflicts so far.'),
    ).toBeTruthy();
    click(screen.getByRole('button', { name: 'Check again' }));
    await waitFor(() => {
      expect(gets(api, `/api/projects/${pid}`)).toBe(2);
    });
    expect(gets(api, `/api/projects/${pid}/review`)).toBe(2);
    cleanup();
    show({ [PATH.project]: projectFailed });
    await ready();
    expect(screen.getByText(`Reading stopped: ${String(projectFailed.error)}.`)).toBeTruthy();
  });

  it('CF-17 Open the workspace goes to the engineer route of the first drawing with quantities', async () => {
    show();
    await ready();
    const first = projectReview.drawings.find((d) => d.quantities > 0);
    expect(screen.getByRole('link', { name: 'Open the workspace' }).getAttribute('href')).toBe(
      `#/p/${pid}/d/${String(first?.drawing_id)}/engineer`,
    );
  });

  it('CF-18 each card links to its quantity in the surveyor workspace', async () => {
    show();
    await ready();
    const href =
      within(card(base.label))
        .getByRole('link', { name: 'Open in the surveyor workspace' })
        .getAttribute('href') ?? '';
    expect(href.startsWith(`#/p/${pid}/d/${did}/surveyor?`)).toBe(true);
    expect(new URLSearchParams(href.split('?')[1]).get('q')).toBe(QTY);
  });

  it('CF-19 the side panel links to the conflicts screen when there are conflicts', async () => {
    mockApi({ [PATH.review]: projectReview });
    render(<ProjectReviewSide projectId={pid} drawingId={did} />);
    const link = await screen.findByRole('link', { name: 'Settle the conflicts' });
    expect(link.getAttribute('href')).toBe(`#/p/${pid}/conflicts`);
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

  it('CF-21 the pill is focusable and its tooltip is its accessible description', async () => {
    show();
    await ready();
    const pill = within(card(base.label)).getByText('Settled by rule');
    expect(pill.tabIndex).toBe(0);
    const tip = document.getElementById(pill.getAttribute('aria-describedby') ?? '');
    expect(tip?.textContent).toBe(
      `A rule settled this: ${String(base.conflict.resolution?.rule)}. Modify it if you disagree.`,
    );
  });

  it('CF-23 a real sign-off on the entry locks the card and names the signer', async () => {
    const signed: ConflictEntry = { ...base, signed: { by: 'Ana', at: AT, value: 30 } };
    show({ [PATH.review]: withConflicts([signed]) });
    await ready();
    const c = card(base.label);
    expect(within(c).getByText('Signed off by Ana')).toBeTruthy();
    expect(disabled(tile(c, 'A'))).toBe(true);
    expect(within(c).queryByRole('button', { name: 'Modify' })).toBeNull();
  });

  it('CF-24 a row value no tile has (a recount) presses no tile and reads In use', async () => {
    const { container } = show({ [PATH.review]: withConflicts([{ ...base, value: 27.5 }]) });
    await ready();
    expect(container.querySelector('[data-pending]')).toBeNull();
    const c = card(base.label);
    expect(pressed(tile(c, 'A')) || pressed(tile(c, 'B'))).toBe(false);
    expect(within(c).getByText('In use: 27.50 m².')).toBeTruthy();
  });
});
