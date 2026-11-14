import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { error, project } from '../api/fixtures';
import type { ProjectView } from '../api';
import { mockApi, never, reply } from '../test/mockApi';
import { ProjectScreen } from './ProjectScreen';
import { flush, must, variants } from './testing';

const ID = project.id;
const GET = `GET /api/projects/${ID}`;

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

  it('IN-16 header: name, Done, Cost: $0.00, 3 of 3 files finished, <progress> 3/3', async () => {
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByRole('heading', { name: project.name })).toBeTruthy();
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.getByText('Cost: $0.00', { exact: false })).toBeTruthy();
    expect(screen.getByText('3 of 3 files finished')).toBeTruthy();
    const progress = must(document.querySelector('progress'));
    expect(progress.value).toBe(3);
    expect(progress.max).toBe(3);
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

  it('IN-30 the stage strip lists every stage with its file count, and waiting files', async () => {
    mockApi({ [GET]: variants.queued });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const strip = screen.getByRole('list', { name: 'Pipeline stages' });
    const items = [...strip.querySelectorAll('li')].map((li) => li.textContent);
    expect(items[0]).toBe(`Waiting ${String(project.files.length)}`);
    expect(items.slice(1).map((t) => t.replace(/ \d+.*$/, ''))).toEqual([
      'Unpack',
      'Hash',
      'Identify',
      'Group',
      'Route',
      'Cache',
      'Normalise',
      'Extract',
      'Second count',
      'Takeoff',
      'Write',
    ]);
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
    expect(screen.getByRole('list', { name: 'Pipeline stages' }).textContent).toContain('working');
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

  it('IN-31 the stage holding a running file says "working"; a done project has none', async () => {
    mockApi({ [GET]: variants.running });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    const items = () => [...document.querySelectorAll('.ingest-stages li')];
    const working = items().filter((li) => li.textContent.includes('working'));
    expect(working.map((li) => li.querySelector('span')?.textContent)).toEqual(['Extract']);
    cleanup();
    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(items().some((li) => li.textContent.includes('working'))).toBe(false);
  });

  it('R1-1-1 progress of one file reads "1 of 1 file finished"', async () => {
    mockApi({ [GET]: { ...project, files: [must(project.files[0])] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('1 of 1 file finished')).toBeTruthy();
  });

  it('R1-1-4 a queued project with no files yet gives no verdict: "Waiting for the files…"', async () => {
    mockApi({ [GET]: { ...variants.queued, files: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText('Waiting to start')).toBeTruthy();
    expect(screen.getAllByText('Waiting for the files…')).toHaveLength(2);
    expect(screen.queryByText('This upload has no files.')).toBeNull();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
    expect(screen.queryByText(/0 of 0/)).toBeNull();
    expect(document.querySelector('progress')).toBeNull();
    cleanup();

    mockApi({ [GET]: { ...variants.running, drawings: [] } });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(
      within(screen.getByRole('region', { name: 'Drawings' })).getByText('Waiting for the files…'),
    ).toBeTruthy();
    expect(screen.queryByText(/^No drawings/)).toBeNull();
  });

  it('IN-51 R2-qa-3-d a Cache count above 0 explains the reused files under the strip', async () => {
    const CAPTION =
      'Each file is counted at its last stage. A reused file stops at Cache: an earlier upload already wrote its drawing.';
    mockApi({
      [GET]: {
        ...project,
        files: project.files.map((f) => ({ ...f, stage: 'cache' as const, reused: true })),
      },
    });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.getByText(CAPTION)).toBeTruthy();
    cleanup();

    mockApi({ [GET]: project });
    render(<ProjectScreen projectId={ID} />);
    await flush();
    expect(screen.queryByText(CAPTION)).toBeNull();
  });
});
