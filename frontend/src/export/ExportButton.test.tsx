import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  error as errorBody,
  project,
  projectChecks,
  projectIssues,
  projectList,
  projectReview,
  takeoff,
} from '../api/fixtures';
import { Header } from '../shell/Header';
import { parseRoute } from '../shell/route';
import { mockApi, never, reply, type Route } from '../test/mockApi';
import { DONE_MS } from './ExportButton';

afterEach(cleanup);

const pid = project.id;
const NAME = 'Export scan as CSV';

function routes(extra: Record<string, Route> = {}): Record<string, Route> {
  const perDrawing: Record<string, Route> = Object.fromEntries(
    projectReview.drawings.flatMap((d): [string, Route][] => [
      [`GET /api/drawings/${d.drawing_id}/takeoff`, { ...takeoff, drawing_id: d.drawing_id }],
      [`GET /api/drawings/${d.drawing_id}/model`, { rooms: [], elements: [] }],
    ]),
  );
  return {
    'GET /api/projects': projectList,
    [`GET /api/projects/${pid}`]: project,
    [`GET /api/projects/${pid}/review`]: projectReview,
    [`GET /api/projects/${pid}/issues`]: projectIssues,
    ...perDrawing,
    ...extra,
  };
}

let blobs: Blob[];
let names: string[];
beforeEach(() => {
  blobs = [];
  names = [];
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: (b: Blob) => {
      blobs.push(b);
      return 'blob:scan';
    },
    revokeObjectURL: () => undefined,
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    names.push(this.download);
  });
  return () => {
    vi.restoreAllMocks();
  };
});

const header = (hash: string) => render(<Header route={parseRoute(hash)} />);

describe('ExportButton in the header', () => {
  it('EX-1 sits right after Workspaces on project routes, not on home or account', () => {
    // The header's Documents badge (useIssuesToAnswer) asks the project, then its issues.
    mockApi(routes());
    const { unmount } = header(`#/p/${pid}/conflicts`);
    const button = screen.getByRole('button', { name: NAME });
    const workspaces = screen.getByRole('link', { name: 'Workspaces' });
    expect(workspaces.nextElementSibling?.contains(button)).toBe(true);
    unmount();
    header('#/');
    expect(screen.queryByRole('button', { name: NAME })).toBeNull();
    cleanup();
    header('#/workspaces');
    expect(screen.queryByRole('button', { name: NAME })).toBeNull();
  });

  it('EX-2 downloads one CSV named after the project and today', async () => {
    mockApi(routes());
    header(`#/p/${pid}`);
    fireEvent.click(screen.getByRole('button', { name: NAME }));
    await waitFor(() => {
      expect(names).toHaveLength(1);
    });
    const today = new Date();
    const ymd = [today.getFullYear(), today.getMonth() + 1, today.getDate()]
      .map((n) => String(n).padStart(2, '0'))
      .join('-');
    expect(names[0]).toBe(`sample-project-scan-${ymd}.csv`);
    expect(blobs[0]?.type).toBe('text/csv;charset=utf-8');
    const text = await blobs[0]?.text();
    expect(text).toContain('kind,file,drawing_id');
    expect(text?.split('\r\n').filter((l) => l.startsWith('quantity,'))).toHaveLength(
      projectReview.drawings.length * takeoff.quantities.length,
    );
  });

  it('EX-10 a failed call downloads nothing and says why; clicking again retries', async () => {
    const api = mockApi(routes({ [`GET /api/projects/${pid}/review`]: reply(500, errorBody) }));
    header(`#/p/${pid}`);
    fireEvent.click(screen.getByRole('button', { name: NAME }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(errorBody.detail);
    expect(screen.getByRole('button', { name: NAME }).textContent).toContain('Export failed');
    expect(names).toHaveLength(0);
    const before = api.calls.length;
    fireEvent.click(screen.getByRole('button', { name: NAME }));
    await waitFor(() => {
      expect(api.calls.length).toBeGreaterThan(before);
    });
  });

  it('EX-11 while loading it says Preparing…, is aria-disabled with a reason, and ignores clicks', async () => {
    const api = mockApi(routes({ [`GET /api/projects/${pid}`]: never() }));
    header(`#/p/${pid}`);
    const button = screen.getByRole('button', { name: NAME });
    fireEvent.click(button);
    await waitFor(() => {
      expect(button.getAttribute('aria-disabled')).toBe('true');
    });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.textContent).toContain('Preparing…');
    expect(button.title).toBe("Loading the scan's data");
    const asked = api.calls.filter((c) => c.url === `/api/projects/${pid}`).length;
    fireEvent.click(button);
    await act(async () => {
      await Promise.resolve();
    });
    expect(api.calls.filter((c) => c.url === `/api/projects/${pid}`).length).toBe(asked);
  });

  it('EX-12 after a download it reads Exported, announced, then Export again', async () => {
    mockApi(routes());
    header(`#/p/${pid}`);
    const button = screen.getByRole('button', { name: NAME });
    fireEvent.click(button);
    await waitFor(() => {
      expect(button.textContent).toContain('Exported');
    });
    expect(screen.getByRole('status').textContent).toContain('Exported');
    await waitFor(
      () => {
        expect(button.textContent).toBe('Export');
      },
      { timeout: DONE_MS + 1000 },
    );
  });

  it('EX-13 checks are asked only with a pack, with that pack; issues carry it too', async () => {
    const api = mockApi(routes({ [`GET /api/projects/${pid}/checks`]: projectChecks }));
    header(`#/p/${pid}`);
    fireEvent.click(screen.getByRole('button', { name: NAME }));
    await waitFor(() => {
      expect(names).toHaveLength(1);
    });
    expect(api.calls.some((c) => c.url.includes('/checks'))).toBe(false);
    cleanup();
    header(`#/p/${pid}/issues?pack=fi`);
    fireEvent.click(screen.getByRole('button', { name: NAME }));
    await waitFor(() => {
      expect(names).toHaveLength(2);
    });
    expect(api.calls.map((c) => c.url)).toContain(`/api/projects/${pid}/checks?pack=fi`);
    expect(api.calls.map((c) => c.url)).toContain(`/api/projects/${pid}/issues?pack=fi`);
    const text = await blobs[1]?.text();
    expect(text?.split('\r\n').some((l) => l.startsWith('check,'))).toBe(true);
  });
});
