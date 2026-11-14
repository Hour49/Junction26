import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { drawing, error, info, rulePackFi } from '../api/fixtures';
import type { IssueList } from '../api';
import { flush, must } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';
import { PageViewer } from '../viewer/PageViewer';
import { IssuesScreen } from './IssuesScreen';
import { DRAWING_B, DRAWING_IFC, PID, issueList, issueListFi, issues } from './testing';

vi.mock('../viewer/PageViewer', () => ({ PageViewer: vi.fn(() => <p>the plan</p>) }));
vi.mock('../shell/info', () => ({
  useInfo: () => ({ info, error: null }),
}));

const GET = `GET /api/projects/${PID}/issues`;
const DRAWING = (id: string) => `GET /api/drawings/${id}`;
const routes = (body: unknown = issueList) => ({
  [GET]: body,
  [DRAWING(DRAWING_B)]: drawing,
  [DRAWING(DRAWING_IFC)]: drawing,
});
const viewer = () => must(vi.mocked(PageViewer).mock.lastCall)[0];
const rowOf = (n: number) =>
  must(
    screen
      .getAllByRole('listitem')
      .find((li) => li.querySelector('.is-n')?.textContent === String(n)),
  );
const pick = (n: number) => {
  fireEvent.click(within(rowOf(n)).getAllByRole('button')[0] as HTMLElement);
};
const drawingGets = (api: ReturnType<typeof mockApi>, id: string) =>
  api.calls.filter((c) => c.url.startsWith(`/api/drawings/${id}`)).length;

const scroll = vi.fn();

beforeEach(() => {
  vi.mocked(PageViewer).mockClear();
  Element.prototype.scrollIntoView = scroll;
});
afterEach(cleanup);

describe('IssuesScreen', () => {
  it('IS-1 requests the issues (with ?pack= when set) and shows "Loading issues…"', async () => {
    const api = mockApi({ [GET]: never() });
    render(<IssuesScreen projectId={PID} pack={null} />);
    await flush();
    expect(screen.getByText('Loading issues…')).toBeTruthy();
    expect(api.calls[0]?.url).toBe(`/api/projects/${PID}/issues`);
    cleanup();
    const fi = mockApi({ [GET]: never() });
    render(<IssuesScreen projectId={PID} pack="fi" />);
    await flush();
    expect(fi.calls[0]?.url).toBe(`/api/projects/${PID}/issues?pack=fi`);
  });

  it('IS-2 rows in the API order with n, kind, why, place and state, under their severity heading', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    const ns = [...document.querySelectorAll('.is-n')].map((e) => e.textContent);
    expect(ns).toEqual(issues.map((_, i) => String(i + 1)));
    const first = rowOf(1);
    expect(first.textContent).toContain('Fails a code rule');
    expect(first.textContent).toContain(must(issues[0]).why);
    expect(first.textContent).toContain('plans/flat-b.pdf · floor 1 · page 1');
    expect(first.textContent).toContain('open');
    const group = (name: string) => screen.getByRole('region', { name });
    expect(within(group('Fails a rule')).getAllByRole('listitem')).toHaveLength(1);
    expect(within(group('Needs a person')).getAllByRole('listitem')).toHaveLength(3);
    expect(within(group('Note')).getAllByRole('listitem')).toHaveLength(1);
  });

  it('IS-4 the summary counts by state', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(screen.getByText('3 open · 1 settled · 1 signed off')).toBeTruthy();
  });

  it('IS-5 Kind and State filters keep n; no match offers "Show all"', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    const kind = screen.getByLabelText<HTMLSelectElement>('Kind');
    const state = screen.getByLabelText<HTMLSelectElement>('State');
    expect([...kind.options].map((o) => o.text)).toEqual([
      'All',
      'Fails a code rule (1)',
      'Conflict (1)',
      'Refused answer (1)',
      'Reading flag (1)',
      'Set aside (1)',
    ]);
    expect([...state.options].map((o) => o.text)).toEqual([
      'All',
      'open (3)',
      'settled (1)',
      'signed off (1)',
    ]);
    fireEvent.change(kind, { target: { value: 'set_aside' } });
    expect([...document.querySelectorAll('.is-n')].map((e) => e.textContent)).toEqual(['5']);
    fireEvent.change(state, { target: { value: 'open' } });
    expect(screen.getByText('No issue matches these filters.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Show all' }));
    expect(document.querySelectorAll('.is-n')).toHaveLength(issues.length);
    expect(kind.value).toBe('');
  });

  it('IS-6 the pack note verbatim with a pack; the choose-a-country line without', async () => {
    mockApi(routes(issueListFi));
    render(<IssuesScreen projectId={PID} pack="fi" />);
    await flush();
    expect(screen.getByText(rulePackFi.note)).toBeTruthy();
    cleanup();
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(
      screen.getByText('Choose a country in the header to add building-code checks.'),
    ).toBeTruthy();
  });

  it('IS-7 the first located issue is selected and shown with marks, selection and focus; one drawing load each', async () => {
    const api = mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(rowOf(1).getAttribute('aria-current')).toBe('true');
    const props = viewer();
    expect(props.pages).toEqual(drawing.pages);
    expect(props.marks.map((m) => [m.id, m.n])).toEqual([
      ['i-check', 1],
      ['i-conflict', 2],
    ]);
    expect(props.selected).toBe('i-check');
    expect(props.focus).toEqual({ page: 1, box: must(issues[0]).box });
    expect(drawingGets(api, DRAWING_B)).toBe(1);
    pick(4); // the IFC drawing
    await flush();
    expect(drawingGets(api, DRAWING_IFC)).toBe(1);
    pick(2); // back to the first drawing: cached
    await flush();
    expect(drawingGets(api, DRAWING_B)).toBe(1);
    expect(viewer().selected).toBe('i-conflict');
  });

  it('IS-9 an issue off any drawing says so; a whole-drawing issue has no focus', async () => {
    const api = mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    const before = api.calls.length;
    pick(3);
    await flush();
    expect(screen.getByText('This issue has no place on a drawing.')).toBeTruthy();
    expect(api.calls.length).toBe(before);
    pick(4);
    await flush();
    expect(viewer().focus ?? null).toBeNull();
  });

  it('IS-10 clicking a mark selects its row and scrolls it into view', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    scroll.mockClear();
    must(viewer().onSelect)('i-conflict');
    await flush();
    expect(rowOf(2).getAttribute('aria-current')).toBe('true');
    expect(scroll).toHaveBeenCalled();
  });

  it('IS-11 each row carries its links', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} pack={null} />);
    await flush();
    expect(within(rowOf(2)).getByRole('link', { name: 'Settle' }).getAttribute('href')).toContain(
      `#/p/${PID}/conflicts?`,
    );
    expect(within(rowOf(2)).getByRole('link', { name: 'Open the drawing' })).toBeTruthy();
    expect(
      within(rowOf(5)).getByRole('link', { name: 'Why it was set aside' }).getAttribute('href'),
    ).toBe(`#/p/${PID}/f/f7`);
  });

  it('IS-12 Export (zip, pending) and CSV only, with the pack, only once the list loaded', async () => {
    mockApi({ [GET]: never() });
    render(<IssuesScreen projectId={PID} pack="fi" />);
    await flush();
    expect(screen.queryByRole('link', { name: 'Export' })).toBeNull();
    cleanup();
    mockApi(routes(issueListFi));
    render(<IssuesScreen projectId={PID} pack="fi" />);
    await flush();
    const zip = screen.getByRole('link', { name: 'Export' });
    expect(zip.getAttribute('href')).toBe(`/api/projects/${PID}/issues.zip?pack=fi`);
    expect(zip.hasAttribute('download')).toBe(true);
    expect(zip.getAttribute('data-pending')).toBe('issues.zip');
    expect(screen.getByRole('link', { name: 'CSV only' }).getAttribute('href')).toBe(
      `/api/projects/${PID}/issues.csv?pack=fi`,
    );
  });

  it('IS-13 409 waits for the ingest with Retry; 404 unknown-pack offers the list without; 404 project is ErrorView', async () => {
    let n = 0;
    const api = mockApi({
      [GET]: () => (n++ === 0 ? reply(409, { ...error, code: 'not-allowed' }) : issueList),
      [DRAWING(DRAWING_B)]: drawing,
    });
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(screen.getByText('The issues are listed once the ingest is done.')).toBeTruthy();
    expect(screen.getByRole('link', { name: /project/i }).getAttribute('href')).toBe(`#/p/${PID}`);
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await flush();
    expect(api.calls.filter((c) => c.url.endsWith('/issues')).length).toBe(2);
    expect(document.querySelectorAll('.is-n')).toHaveLength(issues.length);
    cleanup();

    mockApi({ [GET]: reply(404, { ...error, code: 'unknown-pack' }) });
    render(<IssuesScreen projectId={PID} pack="xx" />);
    await flush();
    expect(screen.getByText('These country rules are not available.')).toBeTruthy();
    expect(screen.getByRole('link', { name: /without/i }).getAttribute('href')).toBe(
      `#/p/${PID}/issues`,
    );
    cleanup();

    mockApi({ [GET]: reply(404, error) });
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(screen.getByRole('link', { name: 'Back to workspaces' })).toBeTruthy();
  });

  it('IS-14 no issues says so (the pack variant with a pack)', async () => {
    mockApi({ [GET]: { ...issueList, issues: [] } });
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(screen.getByText('No issues: nothing needs a look.')).toBeTruthy();
    cleanup();
    mockApi({ [GET]: { ...issueListFi, issues: [] } });
    render(<IssuesScreen projectId={PID} pack="fi" />);
    await flush();
    expect(screen.getByText('No issues: nothing needs a look, and no rule failed.')).toBeTruthy();
  });

  it('IS-15 unknown kind, the refused question', async () => {
    const odd = {
      ...must(issues[1]),
      id: 'i-odd',
      kind: 'brand_new',
    } as unknown as IssueList['issues'][number];
    mockApi(routes({ ...issueList, issues: [...issues, odd] }));
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(rowOf(6).textContent).toContain('brand_new');
    expect(rowOf(3).textContent).toContain('Asked: How many saunas are there?');
    expect(rowOf(5).textContent).toContain('a photo, not of a drawing (1600x1200 px)');
  });

  it('IS-16 API strings render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    mockApi(routes({ ...issueList, issues: issues.map((i) => ({ ...i, why: evil, file: evil })) }));
    render(<IssuesScreen projectId={PID} />);
    await flush();
    expect(screen.getAllByText(evil, { exact: false }).length).toBeGreaterThan(0);
    expect(document.querySelector('img')).toBeNull();
  });

  it('IS-17 kind, severity and state carry words, not colour only', async () => {
    mockApi(routes());
    render(<IssuesScreen projectId={PID} />);
    await flush();
    for (const li of document.querySelectorAll('.is-row')) {
      expect(li.querySelector('.is-kind')?.textContent).toMatch(/\w/);
      expect(li.querySelector('.is-state')?.textContent).toMatch(/open|settled|signed off/);
    }
  });
});
