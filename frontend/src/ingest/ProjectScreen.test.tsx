import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { error, fileReadAsPlan, project, projectRunning, triageStarted } from '../api/fixtures';
import type { ProjectView } from '../api';
import { mockApi, never, reply } from '../test/mockApi';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { ConflictsList } from '../surveyor/ConflictsScreen';
import { formatMs } from './ingest';
import { ProjectScreen } from './ProjectScreen';
import { flush, must, triaged, variants } from './testing';

vi.mock('../advanced/AdvancedIngest', () => ({
  AdvancedIngest: vi.fn(() => <p>the advanced view</p>),
}));
vi.mock('../surveyor/ConflictsScreen', () => ({
  ConflictsList: vi.fn(() => <section id="conflicts">the conflicts list</section>),
}));
vi.mock('../shell/issueCount', () => ({ useIssuesToAnswer: vi.fn(() => null) }));

const ID = project.id;
const GET = `GET /api/projects/${ID}`;

beforeEach(() => {
  window.location.hash = `#/p/${ID}`;
  vi.mocked(AdvancedIngest).mockClear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** Answers each poll with the next body; the last one repeats. */
function sequence(...bodies: ProjectView[]) {
  let i = 0;
  return () => bodies[Math.min(i++, bodies.length - 1)];
}
const gets = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.method === 'GET').length;
const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const fakeClock = () => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });

/** The value of a stats cell, by its label. */
function statCell(label: string) {
  const dt = must(
    [...document.querySelectorAll('.ingest-stats dt')].find((d) => d.textContent === label),
  );
  return must(dt.nextElementSibling);
}
const stat = (label: string) => statCell(label).textContent;
const stepRows = () => within(screen.getByRole('list', { name: 'Steps' })).getAllByRole('listitem');
const iconOf = (row: HTMLElement) => within(row).getByRole('img').getAttribute('aria-label');
async function hashTo(hash: string) {
  await act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    return Promise.resolve();
  });
}

describe('ProjectScreen', () => {
  it('IN-15 requests the project and shows "Loading project…" until the first answer', async () => {
    const api = mockApi({ [GET]: never() });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Loading project…')).toBeTruthy();
    expect(api.calls[0]?.url).toBe(`/api/projects/${ID}`);
  });

  it('IN-16 done: name, Done, All 8 steps done, Ready, ring 100, Files through, Drawings ready, Cost', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: project.name })).toBeTruthy();
    expect(screen.getByText('Analysis done')).toBeTruthy(); // IN-84
    expect(must(screen.getByText('Analysis done').closest('.ingest-eyebrow')).className).toContain(
      'ok',
    );
    expect(screen.getByText('All 8 steps done')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Ready' })).toBeTruthy();
    expect(screen.getByRole('img', { name: '100 percent done' })).toBeTruthy();
    expect(stat('Files through')).toBe('3 / 3');
    expect(stat('Drawings ready')).toMatch(
      new RegExp(`^${String(project.drawings.length)}( / \\d+)?$`),
    );
    // IN-86: the demo's 4th stat; project.json has no set-aside file
    expect(stat('Set aside')).toBe('0');
    expect(
      [...document.querySelectorAll('.ingest-stats dt')].map((d) => d.textContent),
    ).not.toContain('Cost');
    // IN-85: the Simple/Advanced segment on its own row under the h1
    expect(must(document.querySelector('.ingest-head')).className).toContain('ingest-head--stack');
  });

  it('IN-86 Set aside counts the files set aside', async () => {
    mockApi({ [GET]: variants.setAside });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Set aside')).toBe('1');
  });

  it('IN-24 running or queued: the next request goes 500 ms after the answer, none before', async () => {
    for (const body of [variants.running, variants.queued]) {
      fakeClock();
      const api = mockApi({ [GET]: body });
      render(<ProjectScreen projectId={ID} />);
      await flush();
      expect(gets(api)).toBe(1);
      await advance(499);
      expect(gets(api)).toBe(1);
      await advance(1);
      await flush();
      expect(gets(api)).toBe(2);
      cleanup();
      vi.useRealTimers();
    }
  });

  it('IN-25 polling stops on the first done or failed answer', async () => {
    fakeClock();
    const api = mockApi({ [GET]: sequence(variants.running, project) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    await advance(500);
    await flush();
    expect(gets(api)).toBe(2);
    await advance(5000);
    await flush();
    expect(gets(api)).toBe(2);
  });

  it('IN-27 unmounting stops polling', async () => {
    fakeClock();
    const api = mockApi({ [GET]: variants.running });
    const { unmount } = render(<ProjectScreen projectId={ID} />);
    await flush();
    unmount();
    await advance(5000);
    await flush();
    expect(gets(api)).toBe(1);
  });

  it('IN-29 a 404 first load shows detail, code and "Back to workspaces"; a network failure offers Retry', async () => {
    mockApi({ [GET]: reply(404, error) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText(error.detail, { exact: false })).toBeTruthy();
    expect(screen.getByText(error.code, { exact: false })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Back to workspaces' }).getAttribute('href')).toBe(
      '#/workspaces',
    );
    cleanup();

    let n = 0;
    const api = mockApi({ [GET]: project });
    const ok = must(api.fetch.getMockImplementation());
    api.fetch.mockImplementation((...args) =>
      n++ === 0 ? Promise.reject(new TypeError('Failed to fetch')) : ok(...args),
    );
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('network', { exact: false })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await flush();
    expect(screen.getByRole('heading', { name: project.name })).toBeTruthy();
  });

  it('IN-72 a done project with no drawings: "Nothing could be read", reasons, no ring, no conflicts link', async () => {
    const nothing: ProjectView = {
      ...variants.noDrawings,
      files: project.files.map((f) => ({
        ...f,
        state: 'set_aside' as const,
        drawing_id: null,
        reason: `not a drawing: ${f.path}`,
      })),
      skipped: [{ path: 'secret.exe', reason: 'not a file type we read' }],
    };
    mockApi({ [GET]: nothing });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    expect(within(panel).getByText('Nothing could be read from this upload')).toBeTruthy();
    for (const f of nothing.files) expect(panel.textContent).toContain(`not a drawing: ${f.path}`);
    expect(panel.textContent).toContain('secret.exe');
    expect(panel.textContent).toContain('not a file type we read');
    expect(screen.queryByRole('region', { name: 'Progress' })).toBeNull();
    expect(screen.queryByRole('img', { name: /percent done/ })).toBeNull();
    expect(screen.queryByText('All 8 steps done')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Settle the conflicts' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Drawings' })).toBeNull();
    // IN-78: the files are listed on Documents now; no conflicts list, no chat row
    expect(screen.queryByRole('region', { name: 'Files' })).toBeNull();
    expect(
      screen.getByRole('link', { name: 'Every file is listed in Documents.' }).getAttribute('href'),
    ).toBe(`#/p/${ID}/documents`);
    expect(screen.queryByText('the conflicts list')).toBeNull();
    expect(screen.queryByText('Start a new chat')).toBeNull();
  });

  it('IN-23 a failed project shows "Ingest failed" and its error, and is not polled', async () => {
    fakeClock();
    const api = mockApi({ [GET]: variants.failed });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Ingest failed')).toBeTruthy();
    expect(screen.getByText('the server restarted during ingest')).toBeTruthy();
    await advance(5000);
    await flush();
    expect(gets(api)).toBe(1);
  });

  it('IN-28 a failed poll keeps the data, says since when and why, and pauses until Retry', async () => {
    fakeClock();
    let n = 0;
    const api = mockApi({
      [GET]: () => [variants.running, reply(500, error), variants.running][Math.min(n++, 2)],
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    await advance(500);
    await flush();
    expect(gets(api)).toBe(2);
    expect(screen.getByRole('heading', { name: project.name })).toBeTruthy();
    expect(
      screen.getByText(
        new RegExp(
          `^Not updating since \\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d UTC: ${error.detail} \\(${error.code}\\)$`,
        ),
      ),
    ).toBeTruthy();
    await advance(5000);
    await flush();
    expect(gets(api)).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await flush();
    expect(gets(api)).toBe(3);
    expect(screen.queryByText(/Not updating since/)).toBeNull();
  });

  it('R1-1-4 a queued project with no files yet gives no verdict: "Waiting for the files…"', async () => {
    mockApi({ [GET]: { ...variants.queued, files: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Waiting to start')).toBeTruthy();
    expect(screen.queryByText('This upload has no files.')).toBeNull();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
    expect(stat('Files through')).toBe('—');
    expect(screen.queryByText('0 / 0')).toBeNull();
    expect(screen.queryByText(/0 \/ 0/)).toBeNull(); // IN-71: nor the step bar's "0 / 0 files"
    cleanup();

    mockApi({ [GET]: { ...variants.running, drawings: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
    expect(screen.queryByText('Nothing could be read from this upload')).toBeNull();
  });

  it('IN-54 the toggle is a group "View": Simple and Advanced links, the current one aria-current', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const group = screen.getByRole('group', { name: 'View' });
    const simple = within(group).getByRole('link', { name: 'Simple' });
    const advanced = within(group).getByRole('link', { name: 'Advanced' });
    expect(simple.getAttribute('href')).toBe(`#/p/${ID}`);
    expect(advanced.getAttribute('href')).toBe(`#/p/${ID}?view=advanced`);
    expect(simple.getAttribute('aria-current')).toBe('page');
    expect(advanced.getAttribute('aria-current')).toBeNull();
    await hashTo(`#/p/${ID}?view=advanced`);
    const group2 = screen.getByRole('group', { name: 'View' });
    expect(
      within(group2).getByRole('link', { name: 'Advanced' }).getAttribute('aria-current'),
    ).toBe('page');
    expect(
      within(group2).getByRole('link', { name: 'Simple' }).getAttribute('aria-current'),
    ).toBeNull();
  });

  it('IN-55 ?view=advanced renders AdvancedIngest with the polled project; toggling adds no request', async () => {
    window.location.hash = `#/p/${ID}?view=advanced`;
    fakeClock();
    const api = mockApi({ [GET]: sequence(variants.running, project) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const last = () => vi.mocked(AdvancedIngest).mock.lastCall?.[0];
    expect(last()?.projectId).toBe(ID);
    expect(last()?.project).toEqual(variants.running);
    expect(screen.getByText('the advanced view')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Progress' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Drawings' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Files' })).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: project.name })).toBeTruthy();

    await hashTo(`#/p/${ID}`);
    expect(screen.getByRole('region', { name: 'Progress' })).toBeTruthy();
    expect(screen.queryByText('the advanced view')).toBeNull();
    await hashTo(`#/p/${ID}?view=advanced`);
    await flush();
    expect(gets(api)).toBe(1);
    await advance(500);
    await flush();
    expect(gets(api)).toBe(2);
    expect(last()?.project).toEqual(project);
  });

  it('IN-57 the eyebrow and step: running "Analysing now" Step 5 Extract; queued "Waiting to start" Step 1 Unpack', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Analysing now')).toBeTruthy();
    expect(screen.getByText('Step 5 of 8')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Extract' })).toBeTruthy();
    cleanup();
    mockApi({ [GET]: variants.queued });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Waiting to start')).toBeTruthy();
    expect(screen.getByText('Step 1 of 8')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Unpack' })).toBeTruthy();
  });

  it('IN-58 the 8 steps: done, working (hint and file bar), waiting; all done when the project is', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const rows = stepRows();
    expect(rows.map(iconOf)).toEqual([
      'done',
      'done',
      'done',
      'done',
      'working',
      'waiting',
      'waiting',
      'waiting',
    ]);
    const working = must(rows[4]);
    expect(working.textContent).toContain('Extract');
    expect(working.textContent).toContain('rooms, doors, windows, fixtures');
    expect(working.textContent).toContain('2 / 3 files');
    cleanup();
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stepRows().map(iconOf)).toEqual(Array<string>(8).fill('done'));
    expect(stepRows().some((r) => r.textContent.includes(' files'))).toBe(false);
    expect(stepRows().map((r) => r.querySelector('.ingest-step-name')?.textContent)).toEqual([
      'Unpack',
      'Identify',
      'Route',
      'Normalise',
      'Extract',
      'Cross-check',
      'Index',
      'Drawing model',
    ]);
  });

  it('IN-60 the ring reads "<n> percent done": 67 running, 0 queued', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('img', { name: '67 percent done' })).toBeTruthy();
    cleanup();
    mockApi({ [GET]: variants.queued });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('img', { name: '0 percent done' })).toBeTruthy();
  });

  it('IN-61 Elapsed is ms when done, the clock minus started_at while running, "—" before it starts', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Elapsed')).toBe(formatMs(project.ms));
    cleanup();
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    vi.setSystemTime(Date.parse(must(projectRunning.started_at)) + 5000);
    mockApi({ [GET]: projectRunning });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Elapsed')).toBe('5.0 s');
    expect(screen.queryByText(/Remaining/)).toBeNull();
    cleanup();
    mockApi({ [GET]: variants.queued });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Elapsed')).toBe('—');
  });

  it('IN-68 Drawings ready: the count over expected_drawings; the count alone while it is null', async () => {
    for (const [body, text] of [
      [project, `${String(project.drawings.length)} / ${String(project.expected_drawings)}`],
      [projectRunning, '0'],
      [variants.queued, '0'],
    ] as const) {
      mockApi({ [GET]: body });
      render(<ProjectScreen projectId={ID} />);
      await flush();
      expect(stat('Drawings ready')).toBe(text);
      expect(document.querySelector('[data-pending]')).toBeNull();
      cleanup();
    }
  });

  it('IN-62 failed: "Ingest failed", "Stopped", the error, and no step list', async () => {
    mockApi({ [GET]: variants.failed });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Ingest failed')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Stopped' })).toBeTruthy();
    expect(screen.getByText('the server restarted during ingest')).toBeTruthy();
    expect(screen.queryByRole('list', { name: 'Steps' })).toBeNull();
    expect(screen.queryByText(/Step \d of 8/)).toBeNull();
  });

  it('IN-44 strings from files render as text (the "Nothing read" card)', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    mockApi({
      [GET]: {
        ...variants.noDrawings,
        files: project.files.map((f, i) => (i === 0 ? { ...f, reason: evil } : f)),
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText(evil)).toBeTruthy();
    expect(document.querySelector('img')).toBeNull();
  });

  it('IN-45 the working marker carries its word', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(iconOf(must(stepRows()[4]))).toBe('working');
  });

  it('IN-74 while running, queued or failed: no Drawings, Files, conflicts list or chat row', async () => {
    for (const body of [variants.running, variants.queued, variants.failed]) {
      mockApi({ [GET]: body });
      render(<ProjectScreen projectId={ID} />);
      await flush();
      expect(screen.queryByRole('region', { name: 'Drawings' })).toBeNull();
      expect(screen.queryByRole('region', { name: 'Files' })).toBeNull();
      expect(screen.queryByText('the conflicts list')).toBeNull();
      expect(screen.queryByText('Start a new chat')).toBeNull();
      cleanup();
    }
  });

  it('IN-75/IN-88 done: the card with the chat row under Ready and the done line, then the conflicts list; nothing else', async () => {
    window.location.hash = `#/p/${ID}?d=abc&q=door`;
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const card = screen.getByRole('region', { name: 'Progress' });
    expect(card.textContent).toContain('5 drawings ready.');
    const list = screen.getByText('the conflicts list');
    const chat = screen.getByRole('button', { name: 'Start a new chat' });
    expect(card.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // IN-88: the chat row is in the card under "Ready", above the steps, once
    expect(card.contains(chat)).toBe(true);
    const steps = screen.getByRole('list', { name: 'Steps' });
    expect(chat.compareDocumentPosition(steps) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(
      within(card).getByRole('heading', { name: 'Ready' }).compareDocumentPosition(chat) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getAllByText('Start a new chat')).toHaveLength(1);
    const props = must(vi.mocked(ConflictsList).mock.lastCall)[0];
    expect(props.projectId).toBe(ID);
    expect(props.query?.get('q')).toBe('door'); // an issue link focuses its card
    expect(screen.queryByRole('link', { name: 'Settle the conflicts' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Drawings' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Files' })).toBeNull();
    // the list's counts reach the done line
    act(() => {
      must(props.onCounts)({ total: 2, needsPerson: 0 });
    });
    expect(card.textContent).toContain('5 drawings ready. Conflicts are below.');
    expect(card.contains(screen.getByRole('link', { name: 'Start a new chat' }))).toBe(true);
    expect(card.contains(screen.getByRole('link', { name: 'Open the workspace' }))).toBe(true);
  });

  it('FT-20 a done project polls again while a file is being read', async () => {
    fakeClock();
    const reading = {
      ...triaged,
      files: triaged.files.map((f) => (f.id === 'f2' ? triageStarted : f)),
    };
    const read = {
      ...triaged,
      files: triaged.files.map((f) => (f.id === 'f2' ? fileReadAsPlan : f)),
    };
    const api = mockApi({ [`GET /api/projects/${triaged.id}`]: sequence(reading, read) });
    render(<ProjectScreen projectId={triaged.id} />);
    await flush();
    await advance(600);
    await advance(600);
    expect(gets(api)).toBe(2);
  });
});
