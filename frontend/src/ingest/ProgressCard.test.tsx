// The pipeline view v5 (ingest.md "Pipeline view v5"): the files by route with their readers, the reader running
// now, live totals, the last phase, the finished sentence; an old server (no step, no phase) still renders.
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { project } from '../api/fixtures';
import type { FileStatus, ProjectView, StepTrace } from '../api';
import { stubResizeObserver } from '../test/resizeObserver';
import { LANE_ROWS, splitPath } from './RouteLanes';
import { ProgressCard } from './ProgressCard';
import { DEMO_READERS, must } from './testing';

beforeEach(stubResizeObserver);
afterEach(cleanup);

const base = must(project.files[0]);
const file = (id: string, changes: Partial<FileStatus>): FileStatus => ({
  ...base,
  id,
  path: `plans/${id}.png`,
  source: null,
  takeoff: {},
  drawing_id: null,
  ...changes,
});
const step = (changes: Partial<StepTrace>): StepTrace => ({
  id: 'judge',
  label: 'Judge',
  did: '',
  at_ms: 0,
  ms: 0,
  cost_usd: 0,
  state: 'done',
  found: {},
  ...changes,
});

/** A demo-config project mid-run: an image in Extract with its reader named, a drawn PDF read, an IFC queued. */
const running: ProjectView = {
  ...project,
  state: 'running',
  finished_at: null,
  conflicts_open: null,
  cost_usd: 0.031,
  readers: DEMO_READERS,
  phase: 'files',
  files: [
    file('img', {
      route: 'raster',
      kind: 'png_plan',
      state: 'running',
      stage: 'extract',
      step: 'Symbol detector, 8 views',
    }),
    file('pdf', {
      route: 'vector',
      kind: 'pdf_vector',
      path: 'plans/a.pdf',
      state: 'ready',
      stage: 'write',
      drawing_id: 'd1',
      takeoff: { room: 5, door: 2, window: 2 },
    }),
    file('ifc', {
      route: null,
      kind: 'ifc',
      path: 'model/house.ifc',
      state: 'queued',
      stage: null,
    }),
  ],
};

const lane = (name: string) => screen.getByRole('region', { name });
const statOf = (label: string) =>
  must([...document.querySelectorAll('.ingest-stats dt')].find((d) => d.textContent === label))
    .nextElementSibling?.textContent;

describe('ProgressCard: pipeline view v5', () => {
  it('IN-100 the files by route, each lane with the readers that route runs here', () => {
    render(<ProgressCard project={running} now={Date.now()} />);
    const routes = screen.getByRole('region', { name: 'Routes' });
    expect(
      within(routes)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['How each file is read', 'Drawn PDF route', 'Image route', 'Not routed yet']);
    const chips = within(lane('Image')).getByRole('list', { name: 'Readers' });
    expect(
      within(chips)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      'running: symbol detector',
      'count arbiter',
      'plan finder',
      'room reader',
      'Carbon',
      'printed scale',
      'second readers (2)',
      'Carbon level check',
    ]);
    expect(
      within(lane('Drawn PDF'))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toContain('schedule reader');
    // a file links to its own page
    expect(
      within(lane('Image')).getByRole('link', { name: 'plans/img.png' }).getAttribute('href'),
    ).toBe(`#/p/${project.id}/f/img`);
  });

  it('IN-106 each file row: its stage and the reader running now; once read, what it found', () => {
    render(<ProgressCard project={running} now={Date.now()} />);
    expect(lane('Image').textContent).toContain('Extract: Symbol detector, 8 views');
    expect(lane('Image').textContent).toContain('1 reading now');
    expect(lane('Drawn PDF').textContent).toContain('5 rooms, 2 doors, 2 windows');
    expect(lane('Drawn PDF').textContent).toContain('1 drawing read');
    expect(lane('Not routed yet').textContent).toContain('waiting for a free reader');
  });

  it('IN-106 a flagged file: what it found, then why it is flagged (no stray stop with no reason)', () => {
    const flagged = (reason: string): ProjectView => ({
      ...running,
      files: [
        file('x', {
          route: 'raster',
          state: 'flagged',
          stage: 'write',
          drawing_id: 'd',
          reason,
          takeoff: { door: 2 },
        }),
      ],
    });
    render(
      <ProgressCard project={flagged('a phone photo read without correction')} now={Date.now()} />,
    );
    expect(lane('Image').textContent).toContain('2 doors. a phone photo read without correction');
    cleanup();
    render(<ProgressCard project={flagged('')} now={Date.now()} />);
    expect(lane('Image').textContent).toContain('2 doors');
    expect(lane('Image').textContent).not.toContain('2 doors.');
  });

  it('IN-107 an old server (no step, no phase, no readers): the stage alone, no reader chips', () => {
    const old: ProjectView = {
      ...running,
      readers: undefined,
      phase: undefined,
      files: running.files.map((f) => ({ ...f, step: undefined })),
    };
    render(<ProgressCard project={old} now={Date.now()} />);
    expect(lane('Image').textContent).toContain('Extract');
    expect(lane('Image').textContent).not.toContain('Symbol detector');
    expect(within(lane('Image')).queryByRole('list', { name: 'Readers' })).toBeNull();
    // no record of the readers: nothing said about them either way
    expect(lane('Image').textContent).not.toContain('No reader for this route');
    expect(screen.getByText('Step 5 of 9')).toBeTruthy(); // IN-111: where the running file is, not the queued one
  });

  it('IN-105 a step seen once stays ticked "ran" after it ends; one no reader name covers is shown too', () => {
    const { rerender } = render(<ProgressCard project={running} now={Date.now()} />);
    const next: ProjectView = {
      ...running,
      files: running.files.map((f) =>
        f.id === 'img' ? { ...f, step: 'Room reader (Gemini)' } : f,
      ),
    };
    rerender(<ProgressCard project={next} now={Date.now()} />);
    const after: ProjectView = {
      ...next,
      files: next.files.map((f) => (f.id === 'img' ? { ...f, step: 'Wall tracer' } : f)),
    };
    rerender(<ProgressCard project={after} now={Date.now()} />);
    const chips = within(within(lane('Image')).getByRole('list', { name: 'Readers' }))
      .getAllByRole('listitem')
      .map((li) => li.textContent);
    expect(chips).toContain('symbol detector✓');
    expect(chips).toContain('room reader✓');
    expect(chips).toContain('running: Wall tracer');
    expect(chips).toContain('Carbon'); // configured, not seen: no tick
  });

  it("IN-101 a route whose reader reads nothing says so (the no-keys server's image route)", () => {
    const files = running.files.map((f) => ({ ...f, step: undefined }));
    render(
      <ProgressCard project={{ ...running, files, readers: project.readers }} now={Date.now()} />,
    );
    expect(lane('Image').textContent).toContain(
      'No reader for this route on this server: nothing on it is counted.',
    );
    expect(within(lane('Image')).queryByText('symbol detector')).toBeNull();
  });

  it('IN-108 live totals: things found, conflicts (— until done), flagged, set aside, cost', () => {
    render(<ProgressCard project={running} now={Date.now()} />);
    expect([...document.querySelectorAll('.ingest-stats dt')].map((d) => d.textContent)).toEqual([
      'Elapsed',
      'Files through',
      'Drawings ready',
      'Things found',
      'Conflicts',
      'Flagged',
      'Set aside',
      'Cost',
    ]);
    expect(statOf('Things found')).toBe('9');
    expect(statOf('Conflicts')).toBe('—');
    expect(statOf('Flagged')).toBe('0');
    expect(statOf('Cost')).toBe('$0.03');
    cleanup();
    render(<ProgressCard project={{ ...project, conflicts_open: 2 }} now={Date.now()} />);
    expect(statOf('Conflicts')).toBe('2');
    expect(statOf('Flagged')).toBe('1');
  });

  it('IN-109 the last phase: Index with what it runs (index_steps), named from the server phase', () => {
    const indexing: ProjectView = {
      ...running,
      phase: 'index',
      files: running.files.map((f) => ({ ...f, state: 'ready', stage: 'write' })),
      index_steps: [
        step({ id: 'judge', label: 'Judge set-aside files', did: '2 kept out' }),
        step({ id: 'evidence', label: 'Evidence index', did: '14 passages', state: 'failed' }),
      ],
    };
    render(<ProgressCard project={indexing} now={Date.now()} />);
    expect(screen.getByText('Step 9 of 9')).toBeTruthy();
    const rows = within(screen.getByRole('list', { name: 'Steps' })).getAllByRole('listitem', {
      name: undefined,
    });
    const index = must(rows.find((r) => r.textContent.startsWith('◌Index')));
    expect(index.textContent).toContain(
      'judging what was set aside, describing the rest, indexing it all for the chat',
    );
    const last = within(index).getByRole('list', { name: 'Last phase' });
    expect(
      within(last)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Judge set-aside files: 2 kept out', 'Evidence index: 14 passages']);
    // the server says index while a file still runs (a file read again): Index all the same
    cleanup();
    render(<ProgressCard project={{ ...indexing, files: running.files }} now={Date.now()} />);
    expect(screen.getByText('Step 9 of 9')).toBeTruthy();
  });

  it('IN-104 done: under "Ready", what was read by which route and what needs a person', () => {
    render(<ProgressCard project={project} now={Date.now()} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Ready' })).toBeTruthy();
    expect(screen.getByText('Read 2 drawn PDFs. 1 flagged file needs a look.')).toBeTruthy();
  });

  it(`IN-110 a lane shows at most ${String(LANE_ROWS)} files, the rest counted with a link to Documents`, () => {
    const many: ProjectView = {
      ...running,
      files: Array.from({ length: LANE_ROWS + 3 }, (_, i) =>
        file(`f${String(i)}`, { route: 'raster', state: 'ready', stage: 'write' }),
      ),
    };
    render(<ProgressCard project={many} now={Date.now()} />);
    expect(within(lane('Image')).getByRole('list', { name: 'Image files' }).children).toHaveLength(
      LANE_ROWS,
    );
    expect(
      within(lane('Image'))
        .getByRole('link', { name: '3 more files in Documents' })
        .getAttribute('href'),
    ).toBe(`#/p/${project.id}/documents`);
  });

  it('IN-113 a long path gives up its folder first: the file name has its own span that does not shrink', () => {
    expect(splitPath('Plan/OG1/Grundriss.pdf')).toEqual(['Plan/OG1/', 'Grundriss.pdf']);
    expect(splitPath('plan.pdf')).toEqual(['', 'plan.pdf']);
    const long = 'Planunterlagen/Architektur/Grundrisse/Obergeschoss-3/Grundriss_OG3.png';
    render(
      <ProgressCard
        project={{ ...running, files: [file('x', { route: 'raster', path: long })] }}
        now={Date.now()}
      />,
    );
    const link = within(lane('Image')).getByRole('link', { name: long }); // the full path is still its name
    expect(link.getAttribute('title')).toBe(long);
    expect(must(link.querySelector('.ingest-name')).textContent).toBe('Grundriss_OG3.png');
    expect(must(link.querySelector('.ingest-name')).className).toContain('shrink-0');
    expect(must(link.querySelector('.ingest-folder')).className).toContain('truncate');
  });

  it('IN-116 (QA R2-A1) a file on a route with no reader is not a drawing ready nor read', () => {
    const png = file('plan', {
      route: 'raster',
      kind: 'png_plan',
      state: 'flagged',
      drawing_id: 'dp',
      source: 'plans/plan.png',
      reason:
        'not read: this setup has no reader for the image route (0 elements, 0 rooms, no scale on the sheet)',
    });
    const pdf = file('pdf', {
      route: 'vector',
      kind: 'pdf_vector',
      state: 'ready',
      drawing_id: 'dv',
      path: 'plans/pdf.pdf',
      source: 'plans/pdf.pdf',
    });
    const drawing = must(project.drawings[0]);
    const mixed: ProjectView = {
      ...project,
      readers: { ...DEMO_READERS, raster: 'hello' },
      files: [pdf, png],
      expected_drawings: 2,
      drawings: [
        { ...drawing, drawing_id: 'dv', route: 'vector', state: 'ready' },
        { ...drawing, drawing_id: 'dp', route: 'raster', state: 'flagged' },
      ],
    };
    render(<ProgressCard project={mixed} now={Date.now()} />);
    const dt = must(
      [...document.querySelectorAll('.ingest-stats dt')].find(
        (d) => d.textContent === 'Drawings ready',
      ),
    );
    expect(must(dt.nextElementSibling).textContent).toBe('1 / 2');
    expect(screen.getByText('Read 1 drawn PDF. 1 not read.')).toBeTruthy();
    // "Flagged" counts files read that need a look: the unread PNG is not one
    const flagged = must(
      [...document.querySelectorAll('.ingest-stats dt')].find((d) => d.textContent === 'Flagged'),
    );
    expect(must(flagged.nextElementSibling).textContent).toBe('0');
    // the lane headers: the drawn PDF was read, the PNG on the image route was not
    expect(lane('Drawn PDF').textContent).toContain('1 file · 1 drawing read');
    expect(lane('Image').textContent).toContain('1 file');
    expect(lane('Image').textContent).not.toContain('drawing read');
  });
});
