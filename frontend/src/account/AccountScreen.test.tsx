import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { ProjectList, ProjectReview } from '../api';
import { project, projectList, projectQuestions, projectReview, takeoff } from '../api/fixtures';
import { flush, must } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';
import { AccountScreen } from './AccountScreen';

const ID = '5e0c1a2b3d4f';
const LIST = 'GET /api/projects';
const PROJECT = `GET /api/projects/${ID}`;
const REVIEW = `GET /api/projects/${ID}/review`;
const QUESTIONS = `GET /api/projects/${ID}/questions`;
const noQuestions = { project_id: ID, questions: [] };
const internal = { detail: 'internal error', code: 'internal' };
const notFound = { detail: `no project ${ID}`, code: 'not-found' };

const OTHER = 'aaaaaaaaaaaa';
const twoProjects: ProjectList = {
  projects: [
    must(projectList.projects[0]),
    { ...must(projectList.projects[0]), id: OTHER, name: 'flat-c.pdf', files: 1, drawings: 1 },
  ],
};

const routes = {
  [LIST]: projectList,
  [PROJECT]: project,
  [REVIEW]: projectReview,
  [QUESTIONS]: noQuestions,
};

const items = () => [...document.querySelectorAll<HTMLElement>('button[aria-pressed]')];
const panel = () => screen.getByRole('region', { name: 'Selected workspace' });

afterEach(cleanup);

describe('AccountScreen list', () => {
  it('renders no main landmark of its own (the shell owns the one <main>)', async () => {
    mockApi(routes);
    const { container } = render(<AccountScreen />);
    await flush();
    expect(container.querySelector('main, [role="main"]')).toBeNull();
    expect(container.querySelector('.account')).not.toBeNull();
  });

  it('AC-1 asks for the list once and shows the loading line', async () => {
    const api = mockApi({ [LIST]: never() });
    render(<AccountScreen />);
    expect(screen.getByText('Loading workspaces…')).toBeTruthy();
    await flush();
    expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(1);
  });

  it('AC-2 the list item, heading and count line', async () => {
    mockApi(routes);
    render(<AccountScreen />);
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: 'Your workspaces' })).toBeTruthy();
    expect(screen.getByText('1 workspace on this server')).toBeTruthy();
    const item = must(items()[0]);
    expect(item.textContent).toContain('sample-project.zip');
    expect(item.textContent).toContain('Ready');
    expect(item.textContent).toContain('Archive · 11 files · 5 drawings');
    expect(item.textContent).toContain('2026-11-14 08:00 UTC');
  });

  it('AC-5 an empty list', async () => {
    const api = mockApi({ [LIST]: { projects: [] } });
    render(<AccountScreen />);
    await flush();
    expect(screen.getByText('No workspaces yet.')).toBeTruthy();
    expect(
      screen.getByRole('link', { name: 'Drop files or try a sample' }).getAttribute('href'),
    ).toBe('#/');
    expect(screen.queryByRole('region', { name: 'Selected workspace' })).toBeNull();
    expect(api.calls).toHaveLength(1);
  });

  it('AC-6 a list error with Retry', async () => {
    const api = mockApi({ [LIST]: reply(500, internal) });
    render(<AccountScreen />);
    await flush();
    expect(screen.getByText('internal error')).toBeTruthy();
    expect(screen.getByText(/code: internal/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await flush();
    expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(2);
  });

  it('AC-7 AC-8 the first item is selected; click, Enter and Space select another', async () => {
    const api = mockApi({
      ...routes,
      [LIST]: twoProjects,
      [`GET /api/projects/${OTHER}`]: { ...project, id: OTHER, name: 'flat-c.pdf' },
      [`GET /api/projects/${OTHER}/review`]: projectReview,
      [`GET /api/projects/${OTHER}/questions`]: noQuestions,
    });
    render(<AccountScreen />);
    await flush();
    const [first, second] = items();
    expect(must(first).tagName).toBe('BUTTON');
    expect(must(first).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(must(second));
    await flush();
    expect(must(items()[1]).getAttribute('aria-pressed')).toBe('true');
    expect(must(items()[0]).getAttribute('aria-pressed')).toBe('false');
    expect(api.calls.some((c) => c.url === `/api/projects/${OTHER}`)).toBe(true);
    expect(api.calls.some((c) => c.url === `/api/projects/${OTHER}/review`)).toBe(true);
    // A native <button> turns Enter and Space into a click: the item stays a button (checked above).
  });

  it('AC-9 a name is text, never HTML', async () => {
    const name = '<img src=x onerror=alert(1)>';
    mockApi({
      [LIST]: { projects: [{ ...must(projectList.projects[0]), name }] },
      [PROJECT]: { ...project, name },
      [REVIEW]: projectReview,
      [QUESTIONS]: noQuestions,
    });
    const { container } = render(<AccountScreen />);
    await flush();
    expect(screen.getAllByText(name).length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('img')).toBeNull();
  });
});

describe('AccountScreen panel', () => {
  it('AC-10 AC-12 the panel head and the links', async () => {
    const api = mockApi(routes);
    render(<AccountScreen />);
    await flush();
    expect(api.calls.map((c) => c.url)).toEqual(
      expect.arrayContaining([`/api/projects/${ID}`, `/api/projects/${ID}/review`]),
    );
    const p = within(panel());
    expect(p.getByText('Archive · created 2026-11-14 08:00 UTC')).toBeTruthy();
    expect(p.getByRole('heading', { name: 'sample-project.zip' })).toBeTruthy();
    expect(p.getByRole('link', { name: 'Open workspace' }).getAttribute('href')).toBe(`#/p/${ID}`);
    expect(screen.getByRole('link', { name: /New workspace/ }).getAttribute('href')).toBe('#/');
  });

  it('AC-11 the stats', async () => {
    mockApi(routes);
    render(<AccountScreen />);
    await flush();
    const cells = [...panel().querySelectorAll('dt')].map((dt) => [
      dt.textContent,
      dt.nextElementSibling?.textContent,
    ]);
    const sum = (k: 'to_review' | 'signed' | 'quantities') =>
      projectReview.drawings.reduce((n, d) => n + d[k], 0);
    expect(cells).toEqual([
      ['Files', String(project.files.length)],
      ['Drawings', String(project.drawings.length)],
      ['Questions', '0'],
      ['To review', String(sum('to_review'))],
      ['Signed off', `${String(sum('signed'))} of ${String(sum('quantities'))}`],
    ]);
    // #121: every stat is real, none is marked pending.
    expect(document.querySelector('[data-pending]')).toBeNull();
  });

  it('AC-13 the panel loading line', async () => {
    mockApi({ [LIST]: projectList, [PROJECT]: never(), [REVIEW]: never(), [QUESTIONS]: never() });
    render(<AccountScreen />);
    await flush();
    expect(within(panel()).getByText('Loading sample-project.zip…')).toBeTruthy();
  });

  it('AC-14 a project error stays in the panel, Retry asks again', async () => {
    let n = 0;
    const api = mockApi({
      [LIST]: projectList,
      [PROJECT]: () => (++n === 1 ? reply(500, internal) : project),
      [REVIEW]: projectReview,
      [QUESTIONS]: noQuestions,
    });
    render(<AccountScreen />);
    await flush();
    expect(within(panel()).getByText('internal error')).toBeTruthy();
    expect(items()).toHaveLength(1);
    fireEvent.click(within(panel()).getByRole('button', { name: 'Retry' }));
    await flush();
    expect(api.calls.filter((c) => c.url === `/api/projects/${ID}`)).toHaveLength(2);
    expect(within(panel()).getByRole('heading', { name: 'sample-project.zip' })).toBeTruthy();
  });

  it('AC-14 a 404 shows in the panel only', async () => {
    mockApi({
      [LIST]: projectList,
      [PROJECT]: reply(404, notFound),
      [REVIEW]: reply(404, notFound),
      [QUESTIONS]: reply(404, notFound),
    });
    render(<AccountScreen />);
    await flush();
    expect(within(panel()).getByText(notFound.detail)).toBeTruthy();
    expect(items()).toHaveLength(1);
  });

  it('AC-15 a review error', async () => {
    let n = 0;
    const api = mockApi({
      ...routes,
      [REVIEW]: () => (++n === 1 ? reply(500, internal) : projectReview),
    });
    render(<AccountScreen />);
    await flush();
    const p = within(panel());
    const values = [...panel().querySelectorAll('dd')].map((d) => d.textContent);
    expect(values).toEqual([
      String(project.files.length),
      String(project.drawings.length),
      '0',
      '–',
      '–',
    ]);
    expect(p.getByText('Review not loaded: internal error (internal)')).toBeTruthy();
    expect(p.getByText('Uploaded sample-project.zip')).toBeTruthy();
    expect(p.getByText('Analysis done')).toBeTruthy();
    fireEvent.click(p.getByRole('button', { name: 'Retry' }));
    await flush();
    expect(api.calls.filter((c) => c.url === `/api/projects/${ID}/review`)).toHaveLength(2);
    expect(p.queryByText(/Review not loaded/)).toBeNull();
  });
});

describe('AccountScreen history', () => {
  const signedReview: ProjectReview = {
    ...projectReview,
    drawings: projectReview.drawings.map((d) =>
      d.drawing_id === takeoff.drawing_id ? { ...d, signed: 1 } : d,
    ),
  };
  const TAKEOFF = `GET /api/drawings/${takeoff.drawing_id}/takeoff`;

  it('AC-22 no takeoff request when nothing is signed', async () => {
    const api = mockApi(routes);
    render(<AccountScreen />);
    await flush();
    expect(api.calls.some((c) => c.url.includes('/takeoff'))).toBe(false);
  });

  it('AC-22 a signed drawing gets its takeoff with the project', async () => {
    const row = must(takeoff.quantities[0]);
    const signed = {
      ...takeoff,
      quantities: [{ ...row, signed: { by: 'Ana', at: '2026-11-14T09:40:00Z', value: 22.401 } }],
    };
    const api = mockApi({ ...routes, [REVIEW]: signedReview, [TAKEOFF]: signed });
    render(<AccountScreen />);
    await flush();
    const urls = api.calls.filter((c) => c.url.includes('/takeoff')).map((c) => c.url);
    expect(urls).toEqual([`/api/drawings/${takeoff.drawing_id}/takeoff?project=${ID}`]);
    expect(within(panel()).getByText(`Signed off: ${row.label}`)).toBeTruthy();
  });

  it('AC-23 a takeoff error', async () => {
    mockApi({ ...routes, [REVIEW]: signedReview, [TAKEOFF]: reply(500, internal) });
    render(<AccountScreen />);
    await flush();
    const p = within(panel());
    expect(p.getByText('Sign-offs not loaded: internal error (internal)')).toBeTruthy();
    expect(p.getByText('Uploaded sample-project.zip')).toBeTruthy();
    expect(p.getByText(/^Settled by a rule: /)).toBeTruthy();
  });

  it('AC-24 glyphs are hidden, titles say the kind', async () => {
    mockApi(routes);
    render(<AccountScreen />);
    await flush();
    const events = within(panel()).getAllByRole('listitem');
    expect(events.length).toBe(3);
    for (const event of events) {
      expect(event.querySelector('[aria-hidden="true"]')).not.toBeNull();
    }
    expect(events.map((e) => e.querySelector('strong')?.textContent.split(' ')[0])).toEqual([
      'Uploaded',
      'Analysis',
      'Settled',
    ]);
  });

  it('AC-27 no user name, avatar or country control', async () => {
    mockApi(routes);
    const { container } = render(<AccountScreen />);
    await flush();
    expect(container.textContent).not.toMatch(/Beatrice|Hour49/);
    expect(container.querySelector('img, select, [role="img"]')).toBeNull();
  });
});

describe('AccountScreen #121 fields', () => {
  it('AC-28 the to-review pill; no conflict pill (the API counts rule-settled ones open)', async () => {
    const base = must(projectList.projects[0]);
    mockApi({
      ...routes,
      [LIST]: {
        projects: [
          { ...base, to_review: 2, conflicts_open: 1 },
          { ...base, id: OTHER, to_review: null, conflicts_open: 0 },
        ],
      },
    });
    render(<AccountScreen />);
    await flush();
    const [first, second] = items();
    expect(must(first).textContent).toContain('2 to review');
    expect(must(first).textContent).not.toMatch(/conflict/);
    expect(must(second).textContent).not.toMatch(/to review|conflict/);
    expect(document.querySelector('[data-pending]')).toBeNull();
  });

  it('AC-29 the questions log is asked for and shows as a stat and events', async () => {
    const api = mockApi({ ...routes, [QUESTIONS]: projectQuestions });
    render(<AccountScreen />);
    await flush();
    expect(api.calls.some((c) => c.url === `/api/projects/${ID}/questions`)).toBe(true);
    const p = within(panel());
    expect(p.getByText('Questions').nextElementSibling?.textContent).toBe('2');
    expect(p.getByText('Asked: How many doors are there?')).toBeTruthy();
    expect(p.getByText('Asked: What colour is the roof?')).toBeTruthy();
  });

  it('AC-30 a questions error: "–", a note and Retry', async () => {
    let n = 0;
    const api = mockApi({
      ...routes,
      [QUESTIONS]: () => (++n === 1 ? reply(500, internal) : projectQuestions),
    });
    render(<AccountScreen />);
    await flush();
    const p = within(panel());
    expect(p.getByText('Questions').nextElementSibling?.textContent).toBe('–');
    expect(p.getByText('Questions not loaded: internal error (internal)')).toBeTruthy();
    expect(p.getByText('Uploaded sample-project.zip')).toBeTruthy();
    fireEvent.click(p.getByRole('button', { name: 'Retry' }));
    await flush();
    expect(api.calls.filter((c) => c.url === `/api/projects/${ID}/questions`)).toHaveLength(2);
    expect(p.getByText('Questions').nextElementSibling?.textContent).toBe('2');
  });
});
