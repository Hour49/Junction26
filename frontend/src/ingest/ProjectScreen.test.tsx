import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { error, fileReadAsPlan, project, projectRunning, triageStarted } from '../api/fixtures';
import type { ProjectView } from '../api';
import { mockApi, never, reply } from '../test/mockApi';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { ConflictsList } from '../surveyor/ConflictsScreen';
import { formatMs, nameParts } from './ingest';
import { NOTHING_ROWS, ProjectScreen, whyRows } from './ProjectScreen';
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

  it('IN-16 done: name, Done, All 9 steps done, Ready, ring 100, Files through, Drawings ready, Cost', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: project.name })).toBeTruthy();
    expect(screen.getByText('Analysis done')).toBeTruthy(); // IN-84
    expect(must(screen.getByText('Analysis done').closest('.ingest-eyebrow')).className).toContain(
      'ok',
    );
    expect(screen.getByText('All 9 steps done')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Ready' })).toBeTruthy();
    expect(screen.getByRole('img', { name: '100 percent done' })).toBeTruthy();
    expect(stat('Files through')).toBe('3 / 3');
    // project.json's 2 raster drawings are on `raster: hello`: not read, so 4 of its 6 are ready (IN-116)
    expect(stat('Drawings ready')).toBe('4 / 6');
    // IN-86: the demo's 4th stat; project.json has no set-aside file
    expect(stat('Set aside')).toBe('0');
    // IN-108 (v5, brief ingest-ui 2026-11-15): Cost is back beside Set aside, with the other live totals
    expect(stat('Cost')).toBe('$0.00');
    // IN-85: the Simple/Advanced segment on its own row under the h1
    expect(must(document.querySelector('.ingest-head')).className).toContain(
      'flex-col items-start',
    ); // ingest-head--stack
  });

  it('IN-114 (QA R2-C3) a 255-character name: the h1 shows 3 lines at most, its name and title stay whole', async () => {
    const name = `${'Bauprojekt_Sanierung_Mehrfamilienhaus_'.repeat(6)}x`.slice(0, 251) + '.zip';
    mockApi({ [GET]: { ...project, name } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const h1 = screen.getByRole('heading', { level: 1, name });
    expect(h1.getAttribute('title')).toBe(name);
    expect(h1.className).toContain('line-clamp-3');
    // IN-121: a break opportunity after each of its separators, so it wraps there before inside a word
    expect(h1.querySelectorAll('wbr')).toHaveLength(nameParts(name).length - 1);
    expect(must(h1.querySelector('wbr')).previousSibling?.textContent).toBe('Bauprojekt_');
    cleanup();
    // the upload line cuts it in the middle, the extension kept; its title is the whole name
    sessionStorage.setItem(`uploaded:${ID}`, JSON.stringify({ name, bytes: 2048 }));
    mockApi({ [GET]: { ...project, name } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const cut = must(screen.getByRole('status', { name: 'Upload received' }).querySelector('span'));
    expect(cut.textContent).toBe(`${name.slice(0, 39)}…${name.slice(-20)}`);
    expect(cut.textContent).toHaveLength(60);
    expect(cut.getAttribute('title')).toBe(name);
    sessionStorage.clear();
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
    expect(screen.queryByText(error.code, { exact: false })).toBeNull(); // R2-C5: no raw code (shared ErrorView)
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
    expect(screen.getByText('cannot reach the server', { exact: false })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await flush();
    expect(screen.getByRole('heading', { name: project.name })).toBeTruthy();
  });

  it('a lone DXF set aside: the Nothing-read card says to upload it with its PDF or PNG in one zip', async () => {
    const f = must(project.files[0]);
    mockApi({
      [GET]: {
        ...variants.noDrawings,
        files: [{ ...f, path: 'floor3.dxf', kind: 'dxf', state: 'set_aside', drawing_id: null }],
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    expect(panel.textContent).toContain(
      'A DXF is read with the PDF or PNG of the same name: put both in one .zip and upload that.',
    );
  });

  it('IN-116 (QA R2-A1) done, its only drawing on a route with no reader: the Nothing-read card, not "Ready"', async () => {
    const f = must(project.files[0]);
    const why =
      'not read: this setup has no reader for the image route (0 elements, 0 rooms, no scale on the sheet)';
    const drawing = must(project.drawings.find((d) => d.route === 'raster'));
    mockApi({
      [GET]: {
        ...project,
        readers: { ...project.readers, raster: 'hello' },
        expected_drawings: 1,
        files: [
          {
            ...f,
            path: 'plan.png',
            kind: 'png_plan',
            route: 'raster',
            state: 'flagged',
            reason: why,
          },
        ],
        drawings: [{ ...drawing, file: 'plan.png' }],
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    expect(panel.textContent).toContain(why);
    expect(screen.queryByRole('heading', { level: 2, name: 'Ready' })).toBeNull();
    expect(screen.queryByRole('img', { name: '100 percent done' })).toBeNull();
    expect(screen.queryByText(/drawings? ready/)).toBeNull();
  });

  it('IN-126 (QA R4-A9) done, its only drawing a screenshot read only to warn: the Nothing-read card, no chat or workspace', async () => {
    const f = must(project.files[0]);
    const why = 'This looks like a screenshot of a web page, not a building drawing.';
    const drawing = must(project.drawings.find((d) => d.route === 'vector'));
    mockApi({
      [GET]: {
        ...project,
        expected_drawings: 1,
        files: [{ ...f, path: 'page.png', state: 'flagged', reason: why }],
        drawings: [{ ...drawing, file: 'page.png', not_a_drawing: true }],
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    expect(panel.textContent).toContain(why); // the backend's flag reason says why
    expect(screen.queryByRole('heading', { level: 2, name: 'Ready' })).toBeNull();
    expect(screen.queryByText(/drawings? ready/)).toBeNull();
    expect(screen.queryByText('Start a new chat')).toBeNull();
    expect(screen.queryByText('Open the workspace')).toBeNull();
  });

  it('IN-126 (QA R4-A9) a screenshot beside a real drawing: 1 ready, and the workspace opens on the real one', async () => {
    const [f1, f2] = [must(project.files[0]), must(project.files[1])];
    const [real, shot] = project.drawings.filter((d) => d.route === 'vector');
    mockApi({
      [GET]: {
        ...project,
        expected_drawings: 2,
        files: [f1, { ...f2, state: 'flagged' }],
        // the screenshot first: the workspace link must still skip it
        drawings: [{ ...must(shot), not_a_drawing: true }, must(real)],
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Drawings ready')).toBe('1 / 2');
    const card = screen.getByRole('region', { name: 'Progress' });
    expect(card.textContent).toContain('1 drawing ready.');
    act(() => {
      must(must(vi.mocked(ConflictsList).mock.lastCall)[0].onCounts)({ total: 0, needsPerson: 0 });
    });
    expect(screen.getByRole('link', { name: 'Open the workspace' }).getAttribute('href')).toBe(
      `#/p/${ID}/d/${must(real).drawing_id}/engineer`,
    );
  });

  it('IN-108 (QA R4-E6) the Conflicts tile counts what the list under it counts', async () => {
    // the server's own count said 0 while the list read "1 conflict found · 1 settled by a rule"
    mockApi({ [GET]: { ...project, conflicts_open: 0 } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Conflicts')).toBe('—'); // the list has not loaded yet
    const onCounts = must(must(vi.mocked(ConflictsList).mock.lastCall)[0].onCounts);
    act(() => {
      onCounts({ total: 1, needsPerson: 0 });
    });
    expect(stat('Conflicts')).toBe('0 open of 1');
    act(() => {
      onCounts({ total: 0, needsPerson: 0 });
    });
    expect(stat('Conflicts')).toBe('0');
  });

  it('no DXF hint when the set-aside files are not DXF', async () => {
    mockApi({
      [GET]: {
        ...variants.noDrawings,
        files: project.files.map((f) => ({ ...f, state: 'set_aside' as const, drawing_id: null })),
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.queryByText(/A DXF is read with/)).toBeNull();
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
    expect(screen.queryByText('All 9 steps done')).toBeNull();
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

  it('IN-128 (QA R4-G4) a 3000-file zip: entries with the same reason are one row, the rows capped', async () => {
    const txt = Array.from({ length: 3000 }, (_, i) => ({
      path: `notes/n${String(i)}.txt`,
      reason: 'plain text, 1 bytes',
    }));
    const odd = Array.from({ length: 20 }, (_, i) => ({
      path: `odd${String(i)}.bin`,
      reason: `not read: kind ${String(i)}`,
    }));
    mockApi({ [GET]: { ...variants.noDrawings, files: [], skipped: [...txt, ...odd] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    const rows = within(panel).getAllByRole('listitem');
    expect(rows).toHaveLength(NOTHING_ROWS);
    const group = must(rows[0]);
    expect(within(group).getByText('3000 files')).toBeTruthy();
    expect(group.textContent).toContain('plain text, 1 bytes');
    expect(group.textContent).toContain('For example: notes/n0.txt, notes/n1.txt, notes/n2.txt');
    expect(group.textContent).not.toContain('notes/n3.txt');
    expect(must(rows[1]).textContent).toContain('odd0.bin');
    // 1 group + 11 of the 20 odd ones shown: 9 more, still on Documents
    expect(panel.textContent).toContain('And 9 more files.');
    expect(
      within(panel).getByRole('link', { name: 'Every file is listed in Documents.' }),
    ).toBeTruthy();
  });

  it('IN-128 under the threshold (3 entries with one reason) each entry keeps its own row, nothing counted', () => {
    const three = ['a.txt', 'b.txt', 'c.txt'].map((path) => ({ path, reason: 'plain text' }));
    expect(whyRows(three)).toEqual(three.map((t) => ({ reason: 'plain text', paths: [t.path] })));
    expect(whyRows([...three, { path: 'd.txt', reason: 'plain text' }])).toEqual([
      { reason: 'plain text', paths: ['a.txt', 'b.txt', 'c.txt', 'd.txt'] },
    ]);
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
    expect(screen.getByText('Step 5 of 9')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Extract' })).toBeTruthy();
    cleanup();
    mockApi({ [GET]: variants.queued });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Waiting to start')).toBeTruthy();
    expect(screen.getByText('Step 1 of 9')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Unpack' })).toBeTruthy();
  });

  it('IN-58 the 9 steps: done, working (hint and file bar), waiting; all done when the project is', async () => {
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
      'waiting',
    ]);
    const working = must(rows[4]);
    expect(working.textContent).toContain('Extract');
    expect(working.textContent).toContain('rooms, doors, windows, fixtures, scale and schedules');
    expect(working.textContent).toContain('2 / 3 files');
    cleanup();
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stepRows().map(iconOf)).toEqual(Array<string>(9).fill('done'));
    expect(stepRows().some((r) => r.textContent.includes(' files'))).toBe(false);
    expect(stepRows().map((r) => r.querySelector('.ingest-step-name')?.textContent)).toEqual([
      'Unpack',
      'Identify',
      'Route',
      'Normalise',
      'Extract',
      'Second count',
      'Takeoff',
      'Store',
      'Index',
    ]);
  });

  it('IN-89 every file finished while the project runs: Step 9 of 9, Index working, no file bar', async () => {
    // every file finished while it runs: the server is in its last phase, which lists its steps when it ends
    mockApi({
      [GET]: { ...variants.running, files: project.files, phase: 'index', index_steps: [] },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Step 9 of 9')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: 'Index' })).toBeTruthy();
    const rows = stepRows();
    expect(rows.map(iconOf)).toEqual([...Array<string>(8).fill('done'), 'working']);
    expect(must(rows[8]).textContent).toContain(
      'judging what was set aside, describing the rest, indexing it all for the chat',
    );
    expect(must(rows[8]).textContent).not.toContain(' files');
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
      [project, `4 / ${String(project.expected_drawings)}`], // 2 of the 6 not read (IN-116)
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
    expect(screen.queryByText(/Step \d of 9/)).toBeNull();
  });

  it('a restart mid-ingest: no 0 ms and no full ring, and a way on (upload again, what was read)', async () => {
    // what the server leaves after a restart: no finished_at, ms 0, the files not reached set aside
    mockApi({
      [GET]: {
        ...variants.failed,
        finished_at: null,
        ms: 0,
        files: project.files.map((f, i) => (i < 2 ? f : { ...f, state: 'set_aside' })),
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(stat('Elapsed')).toBe('—');
    expect(screen.queryByRole('img', { name: /percent done/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'Upload again' }).getAttribute('href')).toBe('#/');
    expect(
      screen.getByRole('link', { name: 'See what was read in Documents' }).getAttribute('href'),
    ).toBe(`#/p/${ID}/documents`);
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
    // project.json's 2 raster drawings are on `raster: hello`: not read, so 4 of its 6 are ready (IN-116)
    expect(card.textContent).toContain('4 drawings ready.');
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
    expect(card.textContent).toContain('4 drawings ready. Conflicts are below.');
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

// Bogdan 2026-11-15: after an upload the extraction view says what the server received, with its file count.
describe('the upload received (UploadBox keeps it for this tab)', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('says the name, size and that the server received it, then the files the server found', async () => {
    sessionStorage.setItem(
      `uploaded:${ID}`,
      JSON.stringify({ name: 'site.zip', bytes: 2 * 2 ** 20 }),
    );
    mockApi({ [GET]: sequence({ ...projectRunning, files: [] }, project) });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const line = () => screen.getByRole('status', { name: 'Upload received' }).textContent;
    expect(line()).toBe('Uploaded: site.zip, 2.0 MB, received by the server. Unpacking…');
    await act(() => new Promise((r) => setTimeout(r, 600)));
    await flush();
    expect(line()).toBe(
      `Uploaded: site.zip, 2.0 MB, received by the server. ${String(project.files.length)} files found.`,
    );
  });

  it('IN-115 (QA R2-C4) an empty zip, done: no files found, not "Unpacking…"; failed with none: nothing unpacked', async () => {
    sessionStorage.setItem(`uploaded:${ID}`, JSON.stringify({ name: 'empty.zip', bytes: 22 }));
    // what the server answers for an empty zip (no-keys backend, 2026-11-15): done, no files, nothing skipped
    mockApi({ [GET]: { ...variants.noFiles, skipped: [], expected_drawings: 0 } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const line = () => screen.getByRole('status', { name: 'Upload received' }).textContent;
    expect(line()).toBe('Uploaded: empty.zip, 1 KB, received by the server. No files found in it.');
    const panel = screen.getByRole('region', { name: 'Nothing read' });
    expect(within(panel).getByText('There were no files in it.')).toBeTruthy();
    cleanup();
    mockApi({ [GET]: { ...variants.failed, files: [], drawings: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(line()).toBe('Uploaded: empty.zip, 1 KB, received by the server. Nothing was unpacked.');
  });

  it('nothing kept (the sample, another tab): no upload line', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.queryByRole('status', { name: 'Upload received' })).toBeNull();
  });
});
