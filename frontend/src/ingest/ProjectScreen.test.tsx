import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { error, project, projectRunning } from '../api/fixtures';
import type { ProjectView } from '../api';
import { mockApi, never, reply } from '../test/mockApi';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { formatMs } from './ingest';
import { ProjectScreen } from './ProjectScreen';
import { flush, must, variants } from './testing';

vi.mock('../advanced/AdvancedIngest', () => ({
  AdvancedIngest: vi.fn(() => <p>the advanced view</p>),
}));

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

function rowOf(path: string) {
  return must(
    within(screen.getByRole('region', { name: 'Files' }))
      .getByText(path)
      .closest('a'),
  );
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
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.getByText('All 8 steps done')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Ready' })).toBeTruthy();
    expect(screen.getByRole('img', { name: '100 percent done' })).toBeTruthy();
    expect(stat('Files through')).toBe('3 / 3');
    expect(stat('Drawings ready')).toMatch(
      new RegExp(`^${String(project.drawings.length)}( / \\d+)?$`),
    );
    expect(stat('Cost')).toBe('$0.00');
  });

  it('IN-18 each file is a row in order with path, kind, state, reason, size, time, linking to its trace', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const rows = within(screen.getByRole('region', { name: 'Files' })).getAllByRole('link');
    expect(rows.map((r) => r.querySelector('.path')?.textContent)).toEqual(
      project.files.map((f) => f.path),
    );
    project.files.forEach((f, i) => {
      const row = must(rows[i]);
      expect(row.getAttribute('href')).toBe(`#/p/${ID}/f/${f.id}`);
      expect(row.textContent).toContain(must(f.kind));
      expect(row.textContent).toContain(f.state === 'ready' ? 'ready' : 'flagged');
      expect(row.textContent).toContain(f.reason);
      expect(row.textContent).toMatch(/\d+(\.\d)? (B|KB|MB)/);
      expect(row.textContent).toMatch(/ms|s\b/);
    });
  });

  it('IN-19 set aside and text only rows show their word and reason', async () => {
    mockApi({ [GET]: variants.setAside });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const row = rowOf(must(project.files[0]).path);
    expect(row.textContent).toContain('set aside');
    expect(row.textContent).toContain('not a drawing');
    cleanup();
    mockApi({ [GET]: variants.textOnly });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const text = rowOf(must(project.files[0]).path);
    expect(text.textContent).toContain('text only');
    expect(text.textContent).toContain('text and no drawing');
  });

  it('IN-21 each drawing is a card with file, kind, route, state, other renderings and an Open link', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const region = screen.getByRole('region', { name: 'Drawings' });
    const cards = region.querySelectorAll('li');
    expect(cards).toHaveLength(project.drawings.length);
    project.drawings.forEach((d, i) => {
      const card = must(cards[i]);
      expect(card.textContent).toContain(d.file);
      expect(card.textContent).toContain(must(d.kind));
      expect(card.textContent).toContain(`${must(d.route)} route`);
      expect(card.textContent).toContain(d.state === 'ready' ? 'ready' : 'flagged');
      expect(within(card).getByRole('link', { name: 'Open' }).getAttribute('href')).toBe(
        `#/p/${ID}/d/${d.drawing_id}/engineer`,
      );
    });
    expect(must(cards[0]).textContent).toContain('also: plans/flat-a.png');
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

  it('IN-26 a drawing that appears between two polls gets its card; rows keep their order', async () => {
    fakeClock();
    mockApi({ [GET]: sequence(variants.running, project) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const region = () => screen.getByRole('region', { name: 'Drawings' });
    expect(region().querySelectorAll('li')).toHaveLength(variants.running.drawings.length);
    await advance(500);
    await flush();
    expect(region().querySelectorAll('li')).toHaveLength(project.drawings.length);
    const paths = [...document.querySelectorAll('.ingest-files .path')].map((p) => p.textContent);
    expect(paths).toEqual(project.files.map((f) => f.path));
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

  it('IN-29 a 404 first load shows detail, code and a link home; a network failure offers Retry', async () => {
    mockApi({ [GET]: reply(404, error) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText(error.detail, { exact: false })).toBeTruthy();
    expect(screen.getByText(error.code, { exact: false })).toBeTruthy();
    expect(document.querySelector('a[href="#/"]')).toBeTruthy();
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

  it('IN-44 strings from files render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    mockApi({
      [GET]: {
        ...project,
        files: project.files.map((f, i) => (i === 0 ? { ...f, reason: evil } : f)),
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText(evil)).toBeTruthy();
    expect(document.querySelector('img')).toBeNull();
  });

  it('IN-45 every state badge and the working marker carry their word', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(rowOf(must(project.files[2]).path).textContent).toContain('running');
    expect(rowOf(must(project.files[0]).path).textContent).toContain('ready');
    expect(iconOf(must(stepRows()[4]))).toBe('working');
    for (const badge of document.querySelectorAll('.badge')) {
      expect(badge.textContent).toMatch(/queued|running|ready|flagged|text only|set aside/);
    }
  });

  it('IN-20 reused shows "reused"; kind null shows "not identified"', async () => {
    mockApi({ [GET]: variants.reusedNoKind });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const row = rowOf(must(project.files[0]).path);
    expect(row.textContent).toContain('reused');
    expect(row.textContent).toContain('not identified');
  });

  it('IN-22 no drawings and no files say so', async () => {
    mockApi({ [GET]: variants.noDrawings });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(
      screen.getByText('No drawings: nothing in this upload could be read as a plan.'),
    ).toBeTruthy();
    cleanup();
    mockApi({ [GET]: variants.noFiles });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('This upload has no files.')).toBeTruthy();
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
    expect(screen.getAllByText('Waiting for the files…')).toHaveLength(2);
    expect(screen.queryByText('This upload has no files.')).toBeNull();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
    expect(stat('Files through')).toBe('—');
    expect(screen.queryByText('0 / 0')).toBeNull();
    cleanup();

    mockApi({ [GET]: { ...variants.running, drawings: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(
      within(screen.getByRole('region', { name: 'Drawings' })).getByText('Waiting for the files…'),
    ).toBeTruthy();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
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
      [projectRunning, `0 / ${String(projectRunning.expected_drawings)}`],
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

  it('IN-63 "Settle the conflicts" links to the conflicts screen when done, not while live', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('link', { name: 'Settle the conflicts' }).getAttribute('href')).toBe(
      `#/p/${ID}/conflicts`,
    );
    for (const body of [variants.running, variants.queued]) {
      cleanup();
      mockApi({ [GET]: body });
      render(<ProjectScreen projectId={ID} />);
      await flush();
      expect(screen.queryByRole('link', { name: 'Settle the conflicts' })).toBeNull();
    }
  });

  it('IN-64 file rows are links with /f/f in their href and the path and state word in their text', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const rows = [...document.querySelectorAll('a[href*="/f/f"]')];
    expect(rows).toHaveLength(project.files.length);
    project.files.forEach((f, i) => {
      expect(rows[i]?.textContent).toContain(f.path);
      expect(rows[i]?.textContent).toContain(f.state === 'ready' ? 'ready' : 'flagged');
    });
  });
});
