import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawing, error, takeoff, trace } from '../api/fixtures';
import type { FileTrace } from '../api';
import { mockApi, reply } from '../test/mockApi';
import { FileTraceScreen } from './FileTraceScreen';
import { formatMs, kindLabel, normalisedSteps, routeLabel } from './ingest';
import { flush, must, traceVariants } from './testing';

const PID = trace.project_id;
const FID = trace.file.id;
const GET = `GET /api/projects/${PID}/files/${FID}/trace`;

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const IMG = traceVariants.image.file;
const IMG_GET = `GET /api/projects/${PID}/files/${IMG.id}/trace`;
const DRAWING = `GET /api/drawings/${must(IMG.drawing_id)}`;
const traceGets = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.url.endsWith('/trace')).length;

function showImage(body: FileTrace = traceVariants.image, drawingAnswer: unknown = drawing) {
  const api = mockApi({ [IMG_GET]: body, [DRAWING]: drawingAnswer });
  render(<FileTraceScreen projectId={PID} fileId={IMG.id} />);
  return api;
}

describe('FileTraceScreen', () => {
  it('IN-32 requests the trace, shows "Loading trace…", then the file facts', async () => {
    let answer: (v: unknown) => void = () => undefined;
    const api = mockApi({ [GET]: new Promise((r) => (answer = r)) });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByText('Loading trace…')).toBeTruthy();
    expect(api.calls[0]?.url).toBe(`/api/projects/${PID}/files/${FID}/trace`);
    answer(trace);
    await flush();
    const f = trace.file;
    const text = document.body.textContent;
    expect(screen.getByRole('heading', { name: f.path })).toBeTruthy();
    for (const s of [
      f.reason,
      kindLabel(f.kind),
      routeLabel(f.route), // IN-83: "drawn PDF route", not "vector"
      must(f.source),
      must(f.group),
      '$0.00',
    ])
      expect(text).toContain(s);
    expect(text).toContain('ready');
    expect(text).toContain(must(f.sha256).slice(0, 12));
    expect(must(document.querySelector('.ingest-facts')).textContent).not.toContain(must(f.sha256));
    expect(text).toMatch(/\d\.\d KB/);
    // pre-QA: the Read from fact holds the path only, and the eyebrow has one marker (the badge, no dot)
    expect(must(document.querySelector('.ingest-facts')).textContent).not.toContain('read from');
    expect(document.querySelector('.ingest-head .ingest-dot')).toBeNull();
    const route = [...document.querySelectorAll('.ingest-facts dt')].find(
      (d) => d.textContent === 'Route',
    );
    expect(must(route).nextElementSibling?.textContent).toBe(routeLabel(f.route));
  });

  it('IN-33 every stage in order with label, did, ms; output only when it adds something', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const items = [...document.querySelectorAll('.ingest-trace li')];
    expect(items).toHaveLength(trace.stages.length);
    trace.stages.forEach((s, i) => {
      const item = must(items[i]);
      expect(item.textContent).toContain(s.did);
      expect(item.textContent).toContain(formatMs(s.ms));
      expect(item.querySelector('.output')?.textContent ?? null).toBe(
        s.output && s.output !== s.did ? s.output : null,
      );
    });
    expect(must(items[0]).querySelector('b')?.textContent).toBe('Unpack');
    expect(must(items.at(-1)).querySelector('b')?.textContent).toBe('Store');
  });

  it('IN-37 a file with a drawing links "Open the drawing" to its engineer workspace', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByRole('link', { name: 'Open the drawing' }).getAttribute('href')).toBe(
      `#/p/${PID}/d/${must(trace.file.drawing_id)}/engineer`,
    );
  });

  it('IN-43 IN-79 a 404 shows detail, code and "Back to Documents"', async () => {
    mockApi({ [GET]: reply(404, error) });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByText(error.detail, { exact: false })).toBeTruthy();
    expect(screen.getByText(error.code, { exact: false })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Back to Documents' }).getAttribute('href')).toBe(
      `#/p/${PID}/documents`,
    );
  });

  it('IN-44 trace strings render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    mockApi({
      [GET]: { ...trace, stages: trace.stages.map((s, i) => (i === 0 ? { ...s, did: evil } : s)) },
    });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByText(evil)).toBeTruthy();
    expect(document.querySelector('img')).toBeNull();
  });

  it('IN-35 a failed stage reads "Failed: …" with an icon; the file is set aside, no drawing link', async () => {
    mockApi({ [GET]: traceVariants.failed });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const failed = must(document.querySelector('.ingest-trace li.failed'));
    expect(must(failed.querySelector('b')).textContent).toBe('Extract');
    expect(failed.textContent).toContain('Failed: no page could be read');
    expect(failed.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('failed');
    expect(screen.getByText('set aside')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Open the drawing' })).toBeNull();
  });

  it('IN-36 a cache stage reads "Cached: …" with its note, and the file says reused', async () => {
    mockApi({ [GET]: traceVariants.cache });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByText('Cached: ingested before in another project')).toBeTruthy();
    expect(
      screen.getByText('the stages below are from the first ingest of this content'),
    ).toBeTruthy();
    expect(screen.getByText('reused: read before, not recomputed')).toBeTruthy();
  });

  it('IN-38 a running file is polled 500 ms after each answer until finished; unmount stops it', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    let n = 0;
    const api = mockApi({ [GET]: () => (n++ === 0 ? traceVariants.running : trace) });
    const { unmount } = render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    await act(() => vi.advanceTimersByTimeAsync(499));
    expect(traceGets(api)).toBe(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await flush();
    expect(traceGets(api)).toBe(2);
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(traceGets(api)).toBe(2);
    unmount();

    const again = mockApi({ [GET]: traceVariants.running });
    const second = render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    second.unmount();
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(traceGets(again)).toBe(1);
  });

  it('IN-39 the takeoff is a closed <details> "What it ends as: N quantities" listing each key', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const entries = Object.entries(trace.file.takeoff ?? {});
    const details = must(document.querySelector<HTMLDetailsElement>('details.ingest-takeoff'));
    expect(details.open).toBe(false);
    expect(must(details.querySelector('summary')).textContent).toBe(
      `What it ends as: ${String(entries.length)} quantities`,
    );
    const keys = [...details.querySelectorAll('dt')].map((dt) => dt.textContent);
    const values = [...details.querySelectorAll('dd')].map((dd) => dd.textContent);
    expect(keys).toEqual(entries.map(([k]) => k));
    expect(values).toEqual(entries.map(([, v]) => String(v)));
  });

  it('R1-3-5 IN-40 before/after for a normalised image claims no rotation check', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.queryByText('As uploaded')).toBeNull();
    cleanup();

    showImage();
    await flush();
    const before = screen.getByAltText(`${IMG.path} as uploaded`);
    const after = screen.getByAltText(`${IMG.path} after normalisation`);
    expect(before.getAttribute('src')).toBe(
      `/api/projects/${PID}/files/${IMG.id}/preview.png?width=1600`,
    );
    expect(after.getAttribute('src')).toBe(
      `/api/drawings/${must(IMG.drawing_id)}/pages/1.png?width=1600`,
    );
    expect(screen.getByText('As uploaded')).toBeTruthy();
    expect(screen.getByText('After normalisation')).toBeTruthy();
    expect(
      screen.getByText(
        'No turn, deskew or perspective correction applied (rotation is not checked)',
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/already upright/)).toBeNull();
    expect(screen.getByText('1200 × 800 px')).toBeTruthy();
  });

  it('IN-41 normalisedSteps lists what normalisation did', () => {
    const n = must(traceVariants.rotated.file.normalised);
    expect(normalisedSteps(n)).toEqual([
      'EXIF orientation 6 applied',
      'turned 90°',
      'deskewed 1.5°',
    ]);
    expect(normalisedSteps({ ...n, rectified: true }).at(-1)).toBe('perspective corrected');
    expect(normalisedSteps({ ...n, rectified: true, rectifier: 'R1' }).at(-1)).toBe(
      'perspective corrected (R1)',
    );
    expect(normalisedSteps(must(IMG.normalised))).toEqual([]);
  });

  it('IN-42 an image that fails to load is replaced by a line of text', async () => {
    showImage();
    await flush();
    fireEvent.error(screen.getByAltText(`${IMG.path} as uploaded`));
    fireEvent.error(screen.getByAltText(`${IMG.path} after normalisation`));
    expect(screen.getByText('Preview not available')).toBeTruthy();
    expect(screen.getByText('Page not available')).toBeTruthy();
  });

  it('IN-80 no credit on the before/after and no GET /api/drawings/<id> for it', async () => {
    const api = showImage();
    await flush();
    expect(screen.getByText('After normalisation')).toBeTruthy();
    expect(document.body.textContent).not.toContain('Credit');
    expect(api.calls.some((c) => c.url.startsWith('/api/drawings/'))).toBe(false);
  });

  it('AD-100 the stages are open on a time axis under "How it was read: N stages" (was folded, IN-83)', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const region = screen.getByRole('region', { name: 'Stages' });
    expect(region.querySelector('details')).toBeNull();
    expect(
      within(region).getByRole('heading', {
        name: `How it was read: ${String(trace.stages.length)} stages`,
      }),
    ).toBeTruthy();
    expect(region.querySelectorAll('.ingest-trace > li')).toHaveLength(trace.stages.length);
    // equal times: the third stage starts at 2/10 of the axis and is 1/10 long
    const span = must(region.querySelectorAll<HTMLElement>('.tl-span')[2]);
    expect(span.style.getPropertyValue('--l')).toBe('20.00%');
    expect(span.style.getPropertyValue('--w')).toBe('10.00%');
  });

  it('AD-106 the decisions sit in their own region, in pipeline order', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const items = within(screen.getByRole('region', { name: 'Decisions' })).getAllByRole(
      'listitem',
    );
    expect(items.map((li) => li.querySelector('.tl-where')?.textContent)).toEqual([
      'Identify',
      'Route',
      'Second count',
      'Outcome',
    ]);
    expect(must(items[3]).textContent).toContain('Ready to ask');
  });

  it('AD-107 a file whose counts disagree shows both values; one takeoff request, none when they agree', async () => {
    const conflicted = { ...trace, second_count: { measured: 5, conflicts: 1 } };
    const TAKEOFF = `GET /api/drawings/${must(trace.file.drawing_id)}/takeoff`;
    const api = mockApi({ [GET]: conflicted, [TAKEOFF]: takeoff });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    await flush(); // the takeoff is asked once the trace is in
    const region = screen.getByRole('region', { name: 'Decisions' });
    expect(region.textContent).toContain('1 conflict between the counts');
    expect(region.textContent).toContain('22.40 m² on the drawing, 30.00 m² the second way');
    expect(api.calls.filter((c) => c.url.includes('/takeoff'))).toHaveLength(1);
    cleanup();
    const quiet = mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(quiet.calls.some((c) => c.url.includes('/takeoff'))).toBe(false);
  });

  it('R1-1-1 a takeoff of one quantity reads "What it ends as: 1 quantity"', async () => {
    mockApi({ [GET]: { ...trace, file: { ...trace.file, takeoff: { door: 2 } } } });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(must(document.querySelector('.ingest-takeoff summary')).textContent).toBe(
      'What it ends as: 1 quantity',
    );
  });

  it('IN-65 the restyled trace keeps its names; done stages carry "done", a failed one "failed"', async () => {
    mockApi({ [GET]: trace });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    expect(screen.getByRole('link', { name: 'Back to Documents' }).getAttribute('href')).toBe(
      `#/p/${PID}/documents`,
    );
    expect(screen.getByRole('heading', { level: 1, name: trace.file.path })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the drawing' })).toBeTruthy();
    const items = [...document.querySelectorAll('.ingest-trace > li')];
    expect(items).toHaveLength(trace.stages.length);
    items.forEach((li, i) => {
      const s = must(trace.stages[i]);
      expect(li.textContent).toContain(s.did);
      expect(li.textContent).toContain(formatMs(s.ms));
      expect(li.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('done');
    });
    cleanup();
    mockApi({ [GET]: traceVariants.failed });
    render(<FileTraceScreen projectId={PID} fileId={FID} />);
    await flush();
    const failed = must(document.querySelectorAll('.ingest-trace > li')[6]);
    expect(failed.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('failed');
    expect(failed.textContent).toContain('Failed: no page could be read');
  });
});
