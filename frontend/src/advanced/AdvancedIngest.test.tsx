import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawing, error, project, takeoff, trace } from '../api/fixtures';
import type { FileTrace, ProjectView } from '../api';
import { formatSize, nameParts } from '../ingest/ingest';
import { flush, variants, must } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';
import { AdvancedIngest } from './AdvancedIngest';
import { VERDICT_BUTTON } from './visuals';

// The finished block is preqa-a's (src/ingest/IngestFinished.tsx), tested there; here only where it goes (AV-35).
vi.mock('../ingest/IngestFinished', () => ({
  CONFLICTS_ID: 'conflicts',
  DoneLine: (p: { projectId: string; project: ProjectView; counts: unknown }) =>
    p.project.state === 'done' ? (
      <p data-testid="done-line">
        {p.projectId} {JSON.stringify(p.counts)}
      </p>
    ) : null,
  IngestFinished: (p: {
    projectId: string;
    project: ProjectView;
    onCounts?: (c: { total: number; needsPerson: number }) => void;
  }) =>
    p.project.state === 'done' ? (
      <button
        type="button"
        data-testid="finished"
        onClick={() => p.onCounts?.({ total: 3, needsPerson: 1 })}
      >
        {p.projectId}
      </button>
    ) : null,
}));
import { readFileSync } from 'node:fs';

const PID = project.id;
const traceOf = (f: ProjectView['files'][number]): FileTrace => ({ ...trace, file: f });
const TRACE = `GET /api/projects/${PID}/trace`;
const traceSet = (files: FileTrace[]) => ({ project_id: PID, files });

/** Every request the view can make for `p`, answered with fixtures unless overridden. */
function routes(p: ProjectView, over: Record<string, unknown> = {}) {
  const r: Record<string, unknown> = {};
  r[TRACE] = traceSet(p.files.map(traceOf));
  for (const d of p.drawings) {
    r[`GET /api/drawings/${d.drawing_id}/takeoff`] = {
      ...takeoff,
      drawing_id: d.drawing_id,
      file: d.file,
    };
    r[`GET /api/drawings/${d.drawing_id}`] = { ...drawing, id: d.drawing_id, file: d.file };
  }
  return { ...r, ...over };
}

async function show(p: ProjectView = project, over: Record<string, unknown> = {}) {
  const api = mockApi(routes(p, over));
  const view = render(<AdvancedIngest projectId={PID} project={p} />);
  await flush();
  return { api, view };
}

const rail = () => screen.getByRole('navigation', { name: 'Steps' });
const steps = () => within(rail()).getAllByRole('button');
const pick = async (name: RegExp) => {
  fireEvent.click(within(rail()).getByRole('button', { name }));
  await flush();
};
const stat = (label: string) => must(screen.getByText(label, { selector: 'dt' }).parentElement);

afterEach(cleanup);

describe('AdvancedIngest', () => {
  it('AV-1 the rail has the 9 steps in the backend order', async () => {
    await show();
    expect(steps().map((b) => b.textContent.replace(/^[✓–]/, '').split(',')[0])).toEqual([
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

  it('AV-46 the route lines: one per route the project is on, none where the routes do not differ', async () => {
    await show();
    await pick(/^Extract/);
    const list = screen.getByRole('list', { name: 'By route' });
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([expect.stringMatching(/^drawn PDF route: Read from the PDF's text and lines/)]);
    await pick(/^Takeoff/);
    expect(screen.queryByRole('list', { name: 'By route' })).toBeNull();
  });

  it('AV-4 running: the current step is aria-current and selected; done: none current, Takeoff selected', async () => {
    const { view } = await show(variants.running);
    const current = steps().filter((b) => b.getAttribute('aria-current') === 'step');
    expect(current.map((b) => b.textContent.split(',')[0])).toEqual(['Extract']); // working: no icon
    expect(current[0]?.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('heading', { name: 'Extracting' })).toBeTruthy();
    view.unmount();
    await show();
    expect(steps().some((b) => b.hasAttribute('aria-current'))).toBe(false);
    expect(screen.getByRole('heading', { name: 'Working out the quantities' })).toBeTruthy();
  });

  it('AV-5 a click selects a step, and the pick stays when the project updates', async () => {
    const { view } = await show(variants.running);
    await pick(/^Unpack/);
    expect(screen.getByRole('heading', { name: 'Unpacking' })).toBeTruthy();
    view.rerender(<AdvancedIngest projectId={PID} project={{ ...variants.running }} />);
    await flush();
    expect(screen.getByRole('heading', { name: 'Unpacking' })).toBeTruthy();
  });

  it('AV-6 each step names its status in words, and set-aside files', async () => {
    await show(variants.running);
    expect(within(rail()).getByRole('button', { name: /^Unpack, done/ })).toBeTruthy();
    expect(within(rail()).getByRole('button', { name: /^Extract, working/ })).toBeTruthy();
    expect(within(rail()).getByRole('button', { name: /^Index, waiting/ })).toBeTruthy();
    cleanup();
    const aside: ProjectView = {
      ...project,
      files: [{ ...must(project.files[0]), state: 'set_aside', stage: 'route', drawing_id: null }],
      drawings: [],
    };
    await show(aside);
    expect(within(rail()).getByRole('button', { name: /^Route, done.*1 set aside/ })).toBeTruthy();
    expect(
      within(rail()).getByRole('button', { name: /^Normalise, no file got here/ }),
    ).toBeTruthy();
  });

  it('AV-7 heading, explanation, and "Now" only on the current step', async () => {
    await show(variants.running);
    expect(screen.getByText('Now')).toBeTruthy();
    await pick(/^Unpack/);
    expect(screen.queryByText('Now')).toBeNull();
    expect(screen.getByText('Done · replaying what this step did')).toBeTruthy(); // AV-41
    expect(
      screen.getByText(/every path is checked to stay inside the project folder/),
    ).toBeTruthy();
  });

  it('AV-8 the log lists the step lines of every file, failures with icon and word', async () => {
    const failed: FileTrace = {
      ...traceOf(must(project.files[1])),
      stages: trace.stages.map((s, i) => (i === 0 ? { ...s, failure: 'unsafe path' } : s)),
    };
    const files = project.files.map(traceOf);
    files[1] = failed;
    await show(project, { [TRACE]: traceSet(files) });
    await pick(/^Unpack/);
    const log = screen.getByRole('list', { name: 'Log' });
    const items = within(log).getAllByRole('listitem');
    const skips = project.skipped.length; // the Skip lines come first
    expect(items).toHaveLength(skips + 6); // 3 files × unpack + hash
    expect(items[skips]?.textContent).toContain(`Unpack ${must(project.files[0]).path}`);
    expect(log.textContent).toContain('Failed: unsafe path');
  });

  it('AV-9 strings from files render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    const f = { ...must(project.files[0]), path: evil };
    const p: ProjectView = { ...project, files: [f] };
    await show(p, {
      [TRACE]: traceSet([
        { ...trace, file: f, stages: [{ ...must(trace.stages[0]), did: evil, output: evil }] },
      ]),
    });
    await pick(/^Unpack/);
    expect(document.body.textContent).toContain(evil);
    expect(document.querySelector('img[src="x"]')).toBeNull();
  });

  it('AV-10 one project trace request; none before any file has a stage', async () => {
    const traceCalls = (calls: { url: string }[]) => calls.filter((c) => c.url.endsWith('/trace'));
    const { api, view } = await show(variants.queued);
    expect(traceCalls(api.calls)).toHaveLength(0);
    view.unmount();
    const shown = await show(variants.running);
    expect(traceCalls(shown.api.calls).map((c) => c.url)).toEqual([`/api/projects/${PID}/trace`]);
  });

  it('AV-10 the same files do not fetch again; a new stage does', async () => {
    const api = mockApi(routes(variants.running, { [TRACE]: never() }));
    const traces = () => api.calls.filter((c) => c.url.endsWith('/trace'));
    const view = render(<AdvancedIngest projectId={PID} project={variants.running} />);
    await flush();
    view.rerender(<AdvancedIngest projectId={PID} project={{ ...variants.running }} />);
    await flush();
    expect(traces()).toHaveLength(1);
    const moved: ProjectView = {
      ...variants.running,
      files: variants.running.files.map((f) =>
        f.state === 'running' ? { ...f, stage: 'second_count' as const } : f,
      ),
    };
    view.rerender(<AdvancedIngest projectId={PID} project={moved} />);
    await flush();
    expect(traces()).toHaveLength(2);
    view.unmount();
  });

  it('AV-11 a failed trace says so with Retry, which requests it again', async () => {
    let fail = true;
    const { api } = await show(project, {
      [TRACE]: () => (fail ? reply(500, error) : traceSet(project.files.map(traceOf))),
    });
    await pick(/^Unpack/);
    const log = screen.getByRole('list', { name: 'Log' });
    expect(log.textContent).toContain('The trace did not load.');
    fail = false;
    fireEvent.click(within(log).getByRole('button', { name: 'Retry' }));
    await flush();
    expect(api.calls.filter((c) => c.url.endsWith('/trace'))).toHaveLength(2);
    expect(log.textContent).not.toContain('did not load');
    expect(log.textContent).toContain(`Unpack ${must(project.files[0]).path}`);
  });

  it('AV-12 the live line is polite only on the current step', async () => {
    await show(variants.running);
    expect(document.querySelector('.adv-live')?.getAttribute('aria-live')).toBe('polite');
    await pick(/^Unpack/);
    expect(document.querySelector('.adv-live')?.hasAttribute('aria-live')).toBe(false);
  });

  it('AV-13 Unpack stats: files opened, set aside, cost, elapsed = project.ms when done; skipped in the log', async () => {
    await show();
    await pick(/^Unpack/);
    expect(stat('Files opened').textContent).toContain('3 / 3');
    expect(stat('Set aside').textContent).toContain('0');
    expect(stat('Cost').textContent).toContain('$0.00');
    expect(stat('Elapsed').textContent).toContain('12.5 ms');
    const log = screen.getByRole('list', { name: 'Log' });
    expect(log.textContent).toContain(`Skip ${must(project.skipped[0]).path}`);
    expect(document.querySelector('[data-pending]')).toBeNull();
  });

  it('Elapsed while running is now - started_at; before it starts "–"', async () => {
    await show({ ...variants.running, started_at: new Date(Date.now() - 3000).toISOString() });
    await pick(/^Unpack/);
    expect(stat('Elapsed').textContent).toMatch(/3\.\d s/);
    cleanup();
    await show({ ...variants.running, started_at: null });
    await pick(/^Unpack/);
    expect(stat('Elapsed').textContent).toContain('–');
  });

  it('AV-14 the file strip lists every file and scrolls by keyboard', async () => {
    await show();
    await pick(/^Unpack/);
    const strip = screen.getByRole('list', { name: 'Files in this upload' });
    expect(strip.getAttribute('tabindex')).toBe('0');
    for (const f of project.files) expect(strip.textContent).toContain(f.path);
  });

  it('AV-26 Unpack shows each upload itself by kind: preview.png for images and PDFs, else a line', async () => {
    const base = must(project.files[0]);
    const files = [
      { ...base, id: 'p1', path: 'site/plan.jpg', kind: 'photo_plan' as const },
      { ...base, id: 'd1', path: 'docs/spec.pdf', kind: 'pdf_text' as const, drawing_id: null },
      { ...base, id: 'm1', path: 'model/house.ifc', kind: 'ifc' as const },
      { ...base, id: 'c1', path: 'cad/detail.dxf', kind: 'dxf' as const, drawing_id: null },
      { ...base, id: 'q1', path: 'new.bin', kind: null, stage: null, state: 'queued' as const },
    ];
    await show({ ...project, files, drawings: [] });
    await pick(/^Unpack/);
    const strip = screen.getByRole('list', { name: 'Files in this upload' });
    const srcs = [...strip.querySelectorAll('img')].map((i) => i.getAttribute('src'));
    expect(srcs).toEqual([
      `/api/projects/${PID}/files/p1/preview.png?width=400`,
      `/api/projects/${PID}/files/d1/preview.png?width=400`,
    ]);
    expect(strip.textContent).toContain('A model: no picture to show');
    expect(strip.textContent).toContain('DXF: no preview');
    expect(strip.textContent).toContain('photo of a plan'); // kindLabel, never the raw id
    expect(strip.textContent).not.toContain('photo_plan');
    expect(strip.textContent).toContain('Not identified yet');
  });

  it("AV-26 Identify shows the picked file's own preview, or the line for its kind", async () => {
    const ifc = {
      ...must(project.files[0]),
      id: 'm1',
      path: 'model/house.ifc',
      kind: 'ifc' as const,
    };
    await show({ ...project, files: [ifc], drawings: [] });
    await pick(/^Identify/);
    expect(document.querySelector('.adv-figure img')).toBeNull();
    expect(screen.getByText('A model: no picture to show')).toBeTruthy();
  });

  it('AV-26 Normalise shows the upload as it came next to its normalised page', async () => {
    await show();
    await pick(/^Normalise/);
    const d = must(project.drawings[0]);
    const f = must(project.files.find((x) => x.path === d.file));
    expect(screen.getByAltText(`${f.path} as uploaded`).getAttribute('src')).toBe(
      `/api/projects/${PID}/files/${f.id}/preview.png?width=1600`,
    );
    expect(screen.getByAltText(`${d.file}, page 1`)).toBeTruthy();
    expect(screen.getByText('As uploaded')).toBeTruthy();
    expect(screen.getByText('Normalised page 1')).toBeTruthy();
  });

  it('AV-15/16 lanes count by route with reader names; the file lane is marked', async () => {
    await show();
    await pick(/^Route/);
    const lanes = document.querySelectorAll('.adv-lane');
    expect(lanes[0]?.textContent).toContain('Exact geometry');
    expect(lanes[0]?.textContent).toContain('3 files');
    expect(lanes[1]?.textContent).toContain('From the image');
    expect(lanes[1]?.textContent).toContain('not read'); // readers.raster = hello
    expect(lanes[0]?.getAttribute('aria-current')).toBe('true');
    expect(lanes[0]?.textContent).toContain('This file goes here');
    expect(document.body.textContent.toLowerCase()).not.toContain('vision model');
  });

  it("Identify: the scale chip comes from the page scale of the file's drawing", async () => {
    await show();
    await pick(/^Identify/);
    expect(screen.getByText('Scale 1:100 found')).toBeTruthy(); // drawing.json page 1
  });

  it('AV-17 plan counts over drawings; Drawings ready over expected_drawings, ready alone when null', async () => {
    await show();
    await pick(/^Extract/);
    expect(stat('Rooms').textContent).toContain('10');
    expect(stat('Doors').textContent).toContain('4');
    expect(stat('Windows').textContent).toContain('4');
    // AD-123: the two raster drawings were not read (readers.raster = hello), so 4 of the 6 are ready
    expect(stat('Drawings ready').textContent).toContain('4 / 6');
    cleanup();
    await show({ ...project, expected_drawings: null });
    await pick(/^Extract/);
    expect(stat('Drawings ready').querySelector('dd')?.textContent).toBe('4');
  });

  it('AD-123 Drawings ready leaves out drawings on a route with no reader (hello), as the Simple view', async () => {
    await show({ ...project, readers: { ...project.readers, raster: 'composite' } });
    await pick(/^Extract/);
    expect(stat('Drawings ready').textContent).toContain('6 / 6');
    cleanup();
    await show({ ...project, readers: { ...project.readers, raster: 'hello', vector: 'hello' } });
    await pick(/^Extract/);
    expect(stat('Drawings ready').textContent).toContain('1 / 6'); // the IFC alone
  });

  it('AD-127 (QA R4-A9) a drawing called not a drawing is kept and read, tagged, never shown as ready', async () => {
    // flat-b: flagged, read only because the sheet-kind step warns (API.md `not_a_drawing`)
    const p: ProjectView = {
      ...project,
      drawings: project.drawings.map((d) =>
        d.file === 'plans/flat-b.pdf' ? { ...d, not_a_drawing: true } : d,
      ),
    };
    await show(p);
    // Takeoff: the raw total stays, with what it holds under it
    const drawings = must(stat('Drawings').querySelector('dd'));
    expect(drawings.firstChild?.textContent).toBe('6');
    expect(drawings.querySelector('.adv-stat-note')?.textContent).toBe('1 not a drawing');
    const row = (file: string) =>
      must(
        [...document.querySelectorAll('.adv-ready > ul > li')].find((li) =>
          li.textContent.startsWith(`${file}:`),
        ),
      );
    const shot = row('plans/flat-b.pdf');
    expect(shot.textContent).toContain('141 questions ready to ask');
    expect(shot.querySelector('.adv-tag')?.textContent).toBe('not a drawing');
    expect(shot.querySelector('.adv-dot')?.classList.contains('on')).toBe(false);
    const real = row('plans/flat-a.pdf');
    expect(real.querySelector('.adv-tag')).toBeNull();
    expect(real.querySelector('.adv-dot')?.classList.contains('on')).toBe(true);
    // Extract: the picker names it, and the picked drawing carries the tag
    await pick(/^Extract/);
    const select = must(document.querySelector<HTMLSelectElement>('.adv-pick select'));
    expect([...select.options].map((o) => o.textContent)).toContain(
      'plans/flat-b.pdf · not a drawing',
    );
    // readDrawings leaves it out (IN-126): of the 4 read (the 2 raster ones have no reader), 3 are ready
    expect(stat('Drawings ready').textContent).toContain('3 / 6');
    expect(document.querySelector('.adv-visual .adv-tag')).toBeNull(); // flat-a is shown first
    fireEvent.change(select, { target: { value: must(p.drawings[1]).drawing_id } });
    await flush();
    expect(document.querySelector('.adv-visual .adv-tag')?.textContent).toBe('not a drawing');
    // none called so: no note, no tag
    cleanup();
    await show();
    expect(stat('Drawings').querySelector('dd')?.textContent).toBe('6');
    expect(document.querySelector('.adv-tag')).toBeNull();
  });

  it('a room pill names its room_type in its title', async () => {
    const d = must(project.drawings[0]);
    const room = { ...must(takeoff.quantities[0]), key: 'room' };
    await show(project, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: { ...takeoff, quantities: [room] },
    });
    await pick(/^Extract/);
    expect(screen.getByText('Küche').getAttribute('title')).toBe('kitchen');
  });

  it('PlanMarks: marks of different rows may share an id without a duplicate React key', async () => {
    const d = must(project.drawings[0]);
    const door = must(takeoff.quantities[1]);
    const window = { ...door, key: 'window' }; // same mark ids as the door row
    const errors: unknown[] = [];
    const spy = vi.spyOn(console, 'error').mockImplementation((...a: unknown[]) => {
      errors.push(a.join(' '));
    });
    await show(project, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: { ...takeoff, quantities: [door, window] },
    });
    await pick(/^Extract/);
    spy.mockRestore();
    expect(document.querySelectorAll('.adv-plan svg rect')).toHaveLength(4);
    expect(errors.filter((e) => String(e).includes('same key'))).toEqual([]);
  });

  it('AV-18 the plan view draws one rect per page-1 mark of the room, door and window rows', async () => {
    await show();
    await pick(/^Extract/);
    const rects = document.querySelectorAll('.adv-plan svg rect');
    expect(rects).toHaveLength(2); // takeoff.json: the door row's 2 marks
    expect(rects[0]?.getAttribute('x')).toBe(
      String(must(must(takeoff.quantities[1]).marks[0]).box[0]),
    );
  });

  it('AV-19/AV-38 Second count: conflicts first, "Show the conflict" scrolls to the list; stats', async () => {
    await show();
    await pick(/^Second count/);
    const pairs = screen.getByRole('list', { name: 'Measured twice' });
    expect(pairs.textContent).toContain('They disagree. It goes to the conflicts below.');
    expect(within(pairs).queryAllByRole('link')).toHaveLength(0);
    const target = document.createElement('section');
    target.id = 'conflicts';
    target.tabIndex = -1;
    const scroll = vi.fn();
    target.scrollIntoView = scroll;
    document.body.append(target);
    fireEvent.click(must(within(pairs).getAllByRole('button', { name: 'Show the conflict' })[0]));
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(target);
    target.remove();
    expect(stat('Conflicts').textContent).toContain('6'); // one per drawing, 6 drawings
    expect(stat('Agree').textContent).toContain('0');
  });

  it("Second count names each pair by this project's file even when the drawing is shared", async () => {
    const d = must(project.drawings[0]);
    const p: ProjectView = {
      ...project,
      drawings: [{ ...d, file: 'drawings/mine.pdf' }],
      files: project.files.map((f) =>
        f.drawing_id === d.drawing_id ? { ...f, path: 'drawings/mine.pdf' } : f,
      ),
    };
    await show(p, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: {
        ...takeoff,
        drawing_id: d.drawing_id,
        file: 'plans/someone-else.pdf',
      },
    });
    await pick(/^Second count/);
    const pairs = screen.getByRole('list', { name: 'Measured twice' });
    expect(pairs.textContent).toContain('drawings/mine.pdf');
    expect(document.body.textContent).not.toContain('someone-else');
  });

  it('Second count shows every conflict and the first agreeing pairs, the rest behind "Show all"', async () => {
    const agree = (i: number) => ({
      ...must(takeoff.quantities[0]),
      key: `k${String(i)}`,
      status: 'agree' as const,
      second: { method: 'printed_label', value: i }, // six measurements, not one repeated (AD-131)
      conflict: null, // an agreeing row has no conflict
    });
    const long = {
      ...takeoff,
      quantities: [...takeoff.quantities, ...[1, 2, 3, 4, 5, 6].map(agree)],
    };
    const p: ProjectView = { ...project, drawings: [must(project.drawings[0])] };
    const d = must(p.drawings[0]);
    await show(p, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: { ...long, drawing_id: d.drawing_id },
    });
    await pick(/^Second count/);
    const list = screen.getByRole('list', { name: 'Measured twice' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1 + 4);
    fireEvent.click(screen.getByRole('button', { name: 'Show all 7 pairs' }));
    expect(within(list).getAllByRole('listitem')).toHaveLength(7);
  });

  it('AV-31 Second count: "–" until every takeoff has loaded, never a partial count', async () => {
    const last = must(project.drawings.at(-1));
    await show(project, { [`GET /api/drawings/${last.drawing_id}/takeoff`]: never() });
    await pick(/^Second count/);
    for (const label of ['Measured twice', 'Agree', 'Conflicts'])
      expect(stat(label).textContent).toBe(`${label}–`);
    cleanup();
    await show();
    await pick(/^Second count/);
    expect(stat('Measured twice').textContent).not.toContain('–');
  });

  it('AV-34 Second count: Conflicts counts Takeoff.disputes, not every conflict row', async () => {
    const real = must(takeoff.quantities.find((r) => r.status === 'conflict'));
    const twin = { ...real, key: 'area:room|name=Küche' };
    const over: Record<string, unknown> = {};
    for (const d of project.drawings)
      over[`GET /api/drawings/${d.drawing_id}/takeoff`] = {
        ...takeoff,
        drawing_id: d.drawing_id,
        quantities: [...takeoff.quantities, twin],
        disputes: [real.key],
      };
    await show(project, over);
    await pick(/^Second count/);
    expect(stat('Conflicts').textContent).toBe(`Conflicts${String(project.drawings.length)}`);
  });

  it('AV-32 a queued project with no files: no "0 / 0", no "0 files, 0 B"', async () => {
    await show({ ...variants.queued, files: [] });
    await pick(/^Unpack/);
    expect(stat('Files opened').textContent).toBe('Files opened–');
    expect(document.body.textContent).not.toMatch(/0 files|0 \/ 0/);
  });

  it('AV-33 lanes and the Unpack headline in words: no reader ids, no hash', async () => {
    await show();
    await pick(/^Route/);
    const lanes = [...document.querySelectorAll('.adv-lane')].map((l) => l.textContent).join(' ');
    expect(lanes).not.toMatch(/\b(bim|cad|vector|raster):/);
    expect(lanes).toContain('drawn PDF route: PDF vector reader');
    await pick(/^Unpack/);
    const last = must(project.files.at(-1));
    expect(must(document.querySelector('.adv-live')).textContent).toBe(
      `${last.path}: ${formatSize(last.size)}`,
    );
  });

  it('AV-35 done: DoneLine last inside the panel card, IngestFinished after it, counts passed back', async () => {
    await show();
    const card = must(document.querySelector('section.adv-panel'));
    const line = screen.getByTestId('done-line');
    expect(card.lastElementChild).toBe(line);
    expect(line.previousElementSibling?.tagName).toBe('DL');
    const block = screen.getByTestId('finished');
    expect(card.nextElementSibling).toBe(block);
    expect(block.textContent).toBe(PID);
    expect(line.textContent).toBe(`${PID} null`);
    fireEvent.click(block);
    expect(screen.getByTestId('done-line').textContent).toBe(`${PID} {"total":3,"needsPerson":1}`);
  });

  it('AV-36 not done: no done line and no finished block', async () => {
    for (const p of [variants.running, variants.failed, variants.queued]) {
      await show(p);
      expect(screen.queryByTestId('done-line')).toBeNull();
      expect(screen.queryByTestId('finished')).toBeNull();
      cleanup();
    }
  });

  it('AV-37 the Advanced view makes no review or issues request of its own', async () => {
    const { api } = await show();
    await pick(/^Second count/);
    const urls = api.calls.map((c) => c.url);
    expect(urls.length).toBeGreaterThan(0);
    expect(urls.filter((u) => u.includes('/review') || u.includes('/issues'))).toEqual([]);
  });

  it('AV-38 while reading, a conflict goes to the list when reading ends, with no button', async () => {
    await show(variants.running);
    await pick(/^Second count/);
    const pairs = screen.queryByRole('list', { name: 'Measured twice' });
    if (pairs) {
      expect(pairs.textContent).not.toContain('below');
      expect(within(pairs).queryAllByRole('button', { name: 'Show the conflict' })).toHaveLength(0);
      expect(pairs.textContent).toContain(
        'They disagree. It goes to the conflicts when reading ends.',
      );
    }
  });

  it('AV-20/AV-39 Index: questions ready per drawing and the suggestions, no Ask link', async () => {
    await show();
    expect(screen.getByText('Questions ready to ask')).toBeTruthy();
    expect(document.body.textContent).toContain('141 questions ready to ask');
    expect(document.body.textContent).toContain(must(drawing.suggestions[0]).label);
    expect(screen.queryByRole('link', { name: 'Ask this drawing' })).toBeNull();
    expect(document.body.textContent).not.toContain('answers ready');
  });

  it('AD-124 Index: only drawings with questions get a row, the rest one line', async () => {
    // only flat-a's file keeps its takeoff: one row, the other five drawings in one line
    const p: ProjectView = {
      ...project,
      files: project.files.map((f) => (f.path === 'plans/flat-a.pdf' ? f : { ...f, takeoff: {} })),
    };
    await show(p);
    const text = document.body.textContent;
    expect(text).toContain('plans/flat-a.pdf: 141 questions ready to ask');
    expect(text).not.toContain('0 questions ready to ask');
    expect(text).toContain('5 drawings have none yet');
    await show({ ...p, drawings: project.drawings.slice(0, 2) });
    expect(document.body.textContent).toContain('1 drawing has none yet');
  });

  it("AD-125 Index: the log ends with the project's index steps, the live line says the latest", async () => {
    const at = (k: number) => ({ at_ms: k, ms: 1, cost_usd: 0, found: {} });
    const p: ProjectView = {
      ...project,
      files: project.files.map((f, i) =>
        i === 0
          ? { ...f, evidence: { indexed: false, why: 'a floor plan: it is read', cost_usd: 0 } }
          : f,
      ),
      index_steps: [
        { id: 'judge', label: 'Relevance judge', did: '0 files judged', state: 'done', ...at(0) },
        {
          id: 'describe',
          label: 'Files for the evidence index',
          did: '',
          state: 'failed',
          ...at(1),
        },
        {
          id: 'evidence',
          label: 'Evidence index',
          did: 'the index is in step with the project',
          state: 'done',
          ...at(2),
        },
      ],
    };
    await show(p);
    await pick(/^Index/);
    const items = within(screen.getByRole('list', { name: 'Log' })).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual([
      `Index ${must(project.files[0]).path} a floor plan: it is read`,
      'Relevance judge 0 files judged',
      expect.stringMatching(/^Files for the evidence index ✕ Failed: no reason given$/),
      'Evidence index the index is in step with the project',
    ]);
    expect(must(document.querySelector('.adv-live')).textContent).toBe(
      'Evidence index: the index is in step with the project',
    );
  });

  it('AD-125 a path in the live line, the log and Questions ready: folder muted with breaks after "/", name whole', async () => {
    const path = 'plans/site1029/site1029_bldg2117_floor9641.pdf';
    const p: ProjectView = {
      ...project,
      files: project.files.map((f, i) => (i === 0 ? { ...f, path } : f)),
      drawings: project.drawings.map((d, i) => (i === 0 ? { ...d, file: path } : d)),
    };
    await show(p, { [TRACE]: traceSet(p.files.slice(0, 1).map(traceOf)) });
    await pick(/^Takeoff/);
    const live = must(document.querySelector('.adv-live'));
    const log = screen.getByRole('list', { name: 'Log' });
    const name = 'site1029_bldg2117_floor9641.pdf';
    for (const [where, end] of [
      [live, ':'],
      [must(log.querySelector('li')), ''],
    ] as const) {
      expect(where.textContent).toContain(`${path}${end}`);
      const folder = must(where.querySelector('.adv-folder'));
      expect(folder.textContent).toBe('plans/site1029/');
      expect(folder.querySelectorAll('wbr')).toHaveLength(1); // after the inner "/"; the name is its own box
      const box = must(where.querySelector('.adv-name'));
      expect(box.textContent).toBe(`${name}${end}`);
      // after each "_" and ".", for a name wider than the line (AD-126)
      expect(box.querySelectorAll('wbr')).toHaveLength(nameParts(name).length - 1);
    }
    // the Unpack file cards: the same parts
    await pick(/^Unpack/);
    const card = must(document.querySelector('.adv-strip .adv-path'));
    expect(card.textContent).toBe(path);
    expect(card.querySelector('[title]')?.getAttribute('title')).toBe(path);
    expect(must(card.querySelector('.adv-folder')).textContent).toBe('plans/site1029/');
    const cardName = must(card.querySelector('.adv-name'));
    // the parts with a break between each: "site1029_", "bldg2117_", "floor9641.", "pdf" (AD-126)
    expect(cardName.innerHTML).toBe(nameParts(name).join('<wbr>'));
    await pick(/^Takeoff/);
    // Takeoff's visual is "Questions ready to ask"
    const ready = must(document.querySelector('.adv-ready .adv-path'));
    expect(ready.textContent).toBe(`${path}:`);
    expect(ready.querySelector('.adv-name')?.textContent).toBe(`${name}:`);
  });

  it('AV-21 takeoffs only once a step needs them; a failure shows Retry', async () => {
    const d = must(project.drawings[0]);
    const { api } = await show(project, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: reply(500, error),
    });
    expect(api.calls.some((c) => c.url.endsWith('/takeoff'))).toBe(false);
    await pick(/^Extract/);
    expect(api.calls.filter((c) => c.url.endsWith('/takeoff'))).toHaveLength(6);
    expect(screen.getByText(/Could not load the takeoff of/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('AV-22 no design mock values and no Remaining', async () => {
    await show(variants.running);
    const text = document.body.textContent;
    for (const word of ['harbour-block', '1948', 'Swedish', 'Beatrice', 'Remaining', 'Finland'])
      expect(text).not.toContain(word);
  });

  it('AV-24/25 the CSS turns animation off for reduced motion and has no colour literal', () => {
    const pickRule = (css: string) => css.match(/\.adv-pick \{[^}]*\}/)?.[0] ?? '';
    // AV-30: the picker label never breaks inside "File"
    expect(pickRule(readFileSync('src/advanced/advanced.css', 'utf8'))).toContain(
      'overflow-wrap: normal',
    );
    const css = readFileSync('src/advanced/advanced.css', 'utf8');
    expect(css).toMatch(/prefers-reduced-motion: reduce[\s\S]*animation: none/);
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });

  it('AV-39/AV-40 no old screen names, engineer links, credits or refused lines in src/advanced', () => {
    for (const f of ['AdvancedIngest.tsx', 'visuals.tsx', 'advanced.ts']) {
      const src = readFileSync(`src/advanced/${f}`, 'utf8');
      expect(src).not.toMatch(
        /\/engineer|\/conflicts`|Settle the conflicts|Engineer|credit|licen[cs]e|refused/i,
      );
    }
  });

  it('AV-41 CSS: the demo look (kicker ok, done row padding)', () => {
    const css = readFileSync('src/advanced/advanced.css', 'utf8');
    // demo .done-row: 0 32px 28px, phone 0 20px 22px (re-sweep item 4)
    expect(css).toMatch(/\.adv-panel > \.ingest-done-line \{[^}]*padding: 0 32px 28px/);
    expect(css).toMatch(
      /@media \(max-width: 760px\)[^@]*\.adv-panel > \.ingest-done-line \{[^}]*padding: 0 20px 22px/,
    );
    expect(css).toMatch(/\.adv-now\.done \{[^}]*color: var\(--v-ok\)/);
    expect(VERDICT_BUTTON).toContain('min-h-11'); // 44 px
  });

  it('CSS: the set-aside note never wraps', () => {
    const css = readFileSync('src/advanced/advanced.css', 'utf8');
    expect(css).toMatch(/\.adv-aside \{[^}]*white-space: nowrap/);
  });
});
