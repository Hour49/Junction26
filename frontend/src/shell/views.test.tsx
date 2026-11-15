import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { error as errorBody, project } from '../api/fixtures';
import { ProjectScreen } from '../ingest/ProjectScreen';
import { mockApi, reply } from '../test/mockApi';
import { ErrorView, SERVER_DOWN } from './ErrorView';
import { Loading } from './Loading';
import { cleanup } from '@testing-library/react';

afterEach(cleanup);

describe('common views', () => {
  it('SH-38 Loading renders its label as a status', () => {
    render(<Loading label="Loading the project…" />);
    expect(screen.getByRole('status').textContent).toBe('Loading the project…');
  });

  it('SH-39 ErrorView shows detail, code, status and Retry', () => {
    const retry = vi.fn();
    const busy = new ApiError(429, 'busy', 'three projects are being ingested');
    const { unmount } = render(<ErrorView error={busy} onRetry={retry} />);
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('three projects are being ingested');
    expect(alert.textContent).toContain('code: busy');
    expect(alert.textContent).toContain('429');
    expect(screen.queryByRole('link', { name: 'Back to workspaces' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
    unmount();
    render(<ErrorView error={new Error('boom')} />);
    expect(screen.getByRole('alert').textContent).toContain('boom');
    expect(screen.getByRole('alert').textContent).toContain('code: client');
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('QA #430 no answer, 502, 503 and 504 say the server is restarting; the code stays, small', () => {
    for (const down of [
      new ApiError(0, 'network', 'cannot reach the server'),
      ...[502, 503, 504].map(
        (n) => new ApiError(n, `http-${String(n)}`, `the server answered ${String(n)}`),
      ),
    ]) {
      const { unmount } = render(<ErrorView error={down} onRetry={vi.fn()} />);
      const alert = screen.getByRole('alert');
      expect(alert.textContent).toContain(SERVER_DOWN);
      expect(alert.textContent).not.toContain(down.detail);
      expect(alert.textContent).toContain(`code: ${down.code}`);
      expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
      unmount();
    }
    // any other error keeps the server's own words
    render(<ErrorView error={new ApiError(500, 'internal', 'internal error')} />);
    expect(screen.getByRole('alert').textContent).toContain('internal error');
    expect(screen.queryByText(SERVER_DOWN)).toBeNull();
  });

  it('R2-qa-3-2 (SH-48) a 404 offers Back to workspaces, not Retry', () => {
    const retry = vi.fn();
    for (const notFound of [
      new ApiError(404, errorBody.code, errorBody.detail),
      new ApiError(404, 'http-404', 'the server answered 404'),
    ]) {
      const { unmount } = render(<ErrorView error={notFound} onRetry={retry} />);
      const alert = screen.getByRole('alert');
      expect(alert.textContent).toContain(notFound.detail);
      expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
      const back = screen.getByRole('link', { name: 'Back to workspaces' });
      expect(back.getAttribute('href')).toBe('#/workspaces');
      unmount();
    }
    // the status decides: a 500 keeps Retry whatever its code says
    render(
      <ErrorView error={new ApiError(500, errorBody.code, errorBody.detail)} onRetry={retry} />,
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Back to workspaces' })).toBeNull();
  });

  it('R2-qa-3-2 (SH-48) ingest project screen answered 404 shows Back to workspaces, no Retry', async () => {
    mockApi({ [`GET /api/projects/${project.id}`]: reply(404, errorBody) });
    render(<ProjectScreen projectId={project.id} />);
    const back = await screen.findByRole('link', { name: 'Back to workspaces' });
    expect(back.getAttribute('href')).toBe('#/workspaces');
    expect(screen.getByRole('alert').textContent).toContain(errorBody.detail);
    expect(screen.queryByRole('button', { name: /retry/i })).toBeNull();
  });
});
