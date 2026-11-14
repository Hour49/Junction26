import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawing, error, project, projectTrace, takeoff, trace } from '../api/fixtures';
import type { FileTrace, ProjectView } from '../api';
import { flush, variants, must } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';
import { AdvancedIngest } from './AdvancedIngest';
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
  it('AV-1 the rail has the 8 steps in the backend order', async () => {
    await show();
    expect(steps().map((b) => b.textContent.replace(/^[✓–]/, '').split(',')[0])).toEqual([
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

  it('AV-4 running: the current step is aria-current and selected; done: none current, Index selected', async () => {
    const { view } = await show(variants.running);
    const current = steps().filter((b) => b.getAttribute('aria-current') === 'step');
    expect(current.map((b) => b.textContent.split(',')[0])).toEqual(['Extract']); // working: no icon
    expect(current[0]?.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('heading', { name: 'Extracting' })).toBeTruthy();
    view.unmount();
    await show();
    expect(steps().some((b) => b.hasAttribute('aria-current'))).toBe(false);
    expect(screen.getByRole('heading', { name: 'Indexing' })).toBeTruthy();
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
    expect(screen.getByText('Done')).toBeTruthy();
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
    expect(strip.textContent).toContain('No preview for a DXF');
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
    expect(stat('Drawings ready').textContent).toContain('5 / 5');
    cleanup();
    await show({ ...project, expected_drawings: null });
    await pick(/^Extract/);
    expect(stat('Drawings ready').querySelector('dd')?.textContent).toBe('5');
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

  it('AV-19 Cross-check: conflicts first with a link to settle them; stats from the takeoffs', async () => {
    await show();
    await pick(/^Cross-check/);
    const pairs = screen.getByRole('list', { name: 'Measured twice' });
    expect(pairs.textContent).toContain('They disagree. Sent to Settle the conflicts.');
    expect(
      within(pairs).getAllByRole('link', { name: 'Settle the conflicts' })[0]?.getAttribute('href'),
    ).toBe(`#/p/${PID}/conflicts`);
    expect(stat('Conflicts').textContent).toContain('5'); // one per drawing, 5 drawings
    expect(stat('Agree').textContent).toContain('0');
  });

  it("Cross-check names each pair by this project's file even when the drawing is shared", async () => {
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
    await pick(/^Cross-check/);
    const pairs = screen.getByRole('list', { name: 'Measured twice' });
    expect(pairs.textContent).toContain('drawings/mine.pdf');
    expect(document.body.textContent).not.toContain('someone-else');
  });

  it('Cross-check shows every conflict and the first agreeing pairs, the rest behind "Show all"', async () => {
    const agree = (i: number) => ({
      ...must(takeoff.quantities[0]),
      key: `k${String(i)}`,
      status: 'agree' as const,
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
    await pick(/^Cross-check/);
    const list = screen.getByRole('list', { name: 'Measured twice' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1 + 4);
    fireEvent.click(screen.getByRole('button', { name: 'Show all 7 pairs' }));
    expect(within(list).getAllByRole('listitem')).toHaveLength(7);
  });

  it("Cross-check: before the takeoffs load, the counts are the traces' second_count", async () => {
    const r: Record<string, unknown> = { [TRACE]: projectTrace };
    for (const d of project.drawings) r[`GET /api/drawings/${d.drawing_id}/takeoff`] = never();
    await show(project, r);
    await pick(/^Cross-check/);
    expect(stat('Measured twice').textContent).toContain('15'); // project_trace.json f1-f3: 5 each
    expect(stat('Conflicts').textContent).toContain('1');
    expect(stat('Agree').textContent).toContain('14');
  });

  it('AV-20 Index: questions ready per drawing, the suggestions, and Ask this drawing', async () => {
    await show();
    expect(screen.getByText('Questions ready to ask')).toBeTruthy();
    expect(document.body.textContent).toContain('71 questions ready to ask');
    expect(document.body.textContent).toContain(must(drawing.suggestions[0]).label);
    const d = must(project.drawings[0]);
    expect(screen.getAllByRole('link', { name: 'Ask this drawing' })[0]?.getAttribute('href')).toBe(
      `#/p/${PID}/d/${d.drawing_id}/engineer`,
    );
    expect(document.body.textContent).not.toContain('answers ready');
  });

  it('AV-21 takeoffs only once a step needs them; a failure shows Retry', async () => {
    const d = must(project.drawings[0]);
    const { api } = await show(project, {
      [`GET /api/drawings/${d.drawing_id}/takeoff`]: reply(500, error),
    });
    expect(api.calls.some((c) => c.url.endsWith('/takeoff'))).toBe(false);
    await pick(/^Extract/);
    expect(api.calls.filter((c) => c.url.endsWith('/takeoff'))).toHaveLength(5);
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
    const css = readFileSync('src/advanced/advanced.css', 'utf8');
    expect(css).toMatch(/prefers-reduced-motion: reduce[\s\S]*animation: none/);
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });

  it('CSS: the Index links are 44 px tap targets and the set-aside note never wraps', () => {
    const css = readFileSync('src/advanced/advanced.css', 'utf8');
    expect(css).toMatch(/\.adv-ready a \{[^}]*min-height: 44px/);
    expect(css).toMatch(/\.adv-aside \{[^}]*white-space: nowrap/);
  });
});
