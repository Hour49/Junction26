import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { project, trace } from '../api/fixtures';
import type { FileTrace, ProjectView, StageTrace, StepTrace } from '../api';
import { formatMs, routeLabel } from '../ingest/ingest';
import { must, traceVariants } from '../ingest/testing';
import { FileMatrix } from './FileMatrix';
import { TraceTimeline } from './TraceTimeline';

afterEach(cleanup);

const PID = project.id;
const step = (over: Partial<StepTrace>): StepTrace => ({
  id: 'detector',
  label: 'Symbol detector, 8 views',
  did: '',
  at_ms: 0,
  ms: 0,
  cost_usd: 0,
  state: 'done',
  ...over,
});
// shortcut: the contract's fixtures still send steps: [] (trace worker, 2026-11-15); these are our own.
const extract: StageTrace = {
  stage: 'extract',
  did: '7 elements, 5 rooms',
  ms: 4000,
  output: '',
  failure: null,
  cost_usd: 0.012,
  steps: [
    step({ at_ms: 0, ms: 1200, found: { door: 31, window: 12 } }),
    step({
      id: 'rooms',
      label: 'Room reader (Gemini)',
      at_ms: 0,
      ms: 4000,
      cost_usd: 0.012,
      did: '9 rooms',
    }),
    step({ id: 'carbon', label: 'Carbon counter', state: 'skipped' }),
    step({
      id: 'printed_scale',
      label: 'Printed scale',
      at_ms: 1200,
      ms: 300,
      state: 'failed',
      did: 'no scale text',
    }),
  ],
};

const traces = (p: ProjectView, by: (f: ProjectView['files'][number]) => FileTrace) =>
  new Map(p.files.map((f) => [f.id, by(f)]));

describe('TraceTimeline steps', () => {
  it('AD-103 each step with its label, what it found, time, cost; failed and skipped marked; side by side said', () => {
    render(<TraceTimeline stages={[extract]} />);
    const list = screen.getByRole('list', { name: 'Steps of Extract' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows).toHaveLength(4);
    expect(rows[0]?.textContent).toContain('Symbol detector, 8 views');
    expect(rows[0]?.textContent).toContain('31 doors, 12 windows');
    expect(rows[0]?.textContent).toContain(formatMs(1200));
    expect(rows[1]?.textContent).toContain('9 rooms');
    expect(rows[1]?.textContent).toContain('$0.01');
    expect(within(must(rows[2])).getByRole('img').getAttribute('aria-label')).toBe('skipped');
    expect(rows[2]?.textContent).toContain('skipped');
    expect(rows[2]?.querySelector('.tl-track')).toBeNull();
    expect(within(must(rows[3])).getByRole('img').getAttribute('aria-label')).toBe('failed');
    expect(screen.getByText('4 steps inside Extract, up to 2 side by side')).toBeTruthy();
    // the room reader ran for the whole stage, the detector its first 30 %
    const spans = [...list.querySelectorAll<HTMLElement>('.tl-span')];
    expect(spans[0]?.style.getPropertyValue('--w')).toBe('30.00%');
    expect(spans[1]?.style.getPropertyValue('--w')).toBe('100.00%');
    expect(spans[2]?.style.getPropertyValue('--l')).toBe('30.00%');
  });

  it('AD-104 a stage without steps (an old server, or none recorded) draws no step list', () => {
    const old = { ...extract } as Partial<StageTrace>;
    delete old.steps;
    render(<TraceTimeline stages={[old as StageTrace, { ...extract, steps: [] }]} />);
    expect(screen.queryByRole('list', { name: 'Steps of Extract' })).toBeNull();
    expect(screen.getAllByText('7 elements, 5 rooms')).toHaveLength(2);
  });
});

describe('FileMatrix', () => {
  it('AD-110 every file is a row opening its trace, with route, state, time and what it found', () => {
    render(
      <FileMatrix
        projectId={PID}
        project={project}
        traces={traces(project, (f) => ({ ...trace, file: f }))}
      />,
    );
    const region = screen.getByRole('region', { name: 'Files by stage' });
    const rows = within(within(region).getByRole('list', { name: 'Files' })).getAllByRole(
      'listitem',
    );
    expect(rows).toHaveLength(project.files.length);
    project.files.forEach((f, i) => {
      const row = must(rows[i]);
      expect(within(row).getByRole('link', { name: f.path }).getAttribute('href')).toBe(
        `#/p/${PID}/f/${f.id}`,
      );
      // a file read with its group names that file (AD-119), else its route
      expect(row.textContent).toContain(
        f.source && f.source !== f.path
          ? `read with ${f.source}`
          : f.route
            ? routeLabel(f.route)
            : 'not routed',
      );
      if (f.stage) expect(row.textContent).toContain(formatMs(f.ms));
    });
    const pdf = must(rows[project.files.findIndex((f) => f.takeoff?.room !== undefined)]);
    expect(pdf.textContent).toMatch(/\d+ rooms?/);
    // the bar says each stage and its time in words
    expect(
      within(pdf)
        .getByRole('img', { name: /^Unpack .*, Store / })
        .getAttribute('aria-label'),
    ).toContain(`Extract ${formatMs(trace.stages[6]?.ms ?? 0)}`);
  });

  it('AD-111 a failed stage is said on its row; a running file says the step it is on', () => {
    const files = project.files.map((f, i) =>
      i === 0
        ? {
            ...f,
            state: 'running' as const,
            stage: 'extract' as const,
            step: 'Room reader (Gemini)',
          }
        : f,
    );
    const p = { ...project, state: 'running' as const, files };
    render(
      <FileMatrix
        projectId={PID}
        project={p}
        traces={traces(p, (f) =>
          f.id === files[1]?.id ? { ...traceVariants.failed, file: f } : { ...trace, file: f },
        )}
      />,
    );
    const rows = screen.getAllByRole('listitem').filter((li) => li.classList.contains('fm-row'));
    expect(rows[0]?.textContent).toContain('Now: Room reader (Gemini)');
    expect(rows[0]?.querySelector('.fm-seg.now')).not.toBeNull();
    expect(rows[1]?.querySelector('.fm-fail')?.textContent).toBe(
      '✕ Extract failed: no page could be read',
    );
  });

  it('AD-115 a file that found nothing says why on its own full-width line', () => {
    const files = [
      {
        ...must(project.files[0]),
        state: 'set_aside' as const,
        takeoff: {},
        reason: 'a photo, not of a drawing',
      },
    ];
    render(<FileMatrix projectId={PID} project={{ ...project, files }} traces={new Map()} />);
    expect(document.querySelector('.fm-why')?.textContent).toBe('a photo, not of a drawing.');
    expect(document.querySelector('.fm-found')).toBeNull();
  });

  it('AD-119 a file read with its group names that file, not the route as if it were read itself', () => {
    const files = [
      {
        ...must(project.files[0]),
        path: 'plans/flat-a.png',
        source: 'plans/flat-a.pdf',
        route: 'vector' as const,
      },
    ];
    render(<FileMatrix projectId={PID} project={{ ...project, files }} traces={new Map()} />);
    const meta = must(document.querySelector('.fm-meta'));
    expect(meta.textContent).toContain('read with plans/flat-a.pdf');
    expect(meta.textContent).not.toContain('drawn PDF route');
  });

  it('AD-112 bars compare files: the slowest is full width, the others their share', () => {
    const files = project.files.slice(0, 2).map((f, i) => ({ ...f, ms: i === 0 ? 1000 : 250 }));
    render(<FileMatrix projectId={PID} project={{ ...project, files }} traces={new Map()} />);
    const bars = [...document.querySelectorAll<HTMLElement>('.fm-segs')];
    expect(bars.map((b) => b.style.width)).toEqual(['100%', '25%']);
  });

  it('AD-113 the last phase lists its index steps; no files draws nothing', () => {
    const p = {
      ...project,
      phase: 'index' as const,
      index_steps: [
        step({ id: 'judge', label: 'Relevance judge', did: '2 files judged', ms: 900 }),
      ],
    };
    render(<FileMatrix projectId={PID} project={p} traces={new Map()} />);
    expect(screen.getByText('After the files, now: indexing for questions')).toBeTruthy();
    expect(screen.getByRole('list', { name: 'Index steps' }).textContent).toContain(
      '2 files judged',
    );
    cleanup();
    const { container } = render(
      <FileMatrix projectId={PID} project={{ ...project, files: [] }} traces={new Map()} />,
    );
    expect(container.textContent).toBe('');
  });

  it('AD-114 file paths and step words render as text', () => {
    const evil = '<img src=x onerror=alert(1)>';
    const files = [
      { ...must(project.files[0]), path: evil, step: evil, state: 'running' as const },
    ];
    render(<FileMatrix projectId={PID} project={{ ...project, files }} traces={new Map()} />);
    expect(screen.getByText(evil)).toBeTruthy();
    expect(document.querySelector('img[src="x"]')).toBeNull();
  });
});
