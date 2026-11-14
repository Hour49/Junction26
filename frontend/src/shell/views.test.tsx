import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { drawing, error as errorBody } from '../api/fixtures';
import { Credit } from './Credit';
import { ErrorView } from './ErrorView';
import { Loading } from './Loading';
import { cleanup } from '@testing-library/react';

afterEach(cleanup);

describe('common views', () => {
  it('SH-38 Loading renders its label as a status', () => {
    render(<Loading label="Loading the project…" />);
    expect(screen.getByRole('status').textContent).toBe('Loading the project…');
  });

  it('SH-39 ErrorView shows detail, code, status, retry and the start link for not-found', () => {
    const retry = vi.fn();
    const notFound = new ApiError(404, errorBody.code, errorBody.detail);
    const { unmount } = render(<ErrorView error={notFound} onRetry={retry} />);
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain(errorBody.detail);
    expect(alert.textContent).toContain('code: not-found');
    expect(alert.textContent).toContain('404');
    expect(screen.getByRole('link', { name: 'Go to the start' }).getAttribute('href')).toBe('#/');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
    unmount();
    render(<ErrorView error={new Error('boom')} />);
    expect(screen.getByRole('alert').textContent).toContain('boom');
    expect(screen.getByRole('alert').textContent).toContain('code: client');
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('SH-40 Credit shows the credit as text, or that none is recorded', () => {
    const { container, unmount } = render(<Credit credit={drawing.credit ?? null} />);
    expect(container.textContent).toBe('Credit: none recorded for this file');
    unmount();
    const { container: other } = render(<Credit credit="<b>x</b>" />);
    expect(other.textContent).toBe('Credit: <b>x</b>');
    expect(other.querySelector('b')).toBeNull();
  });
});
