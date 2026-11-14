import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, error as errorBody, project, projectReview, takeoff } from '../api/fixtures';
import type { ProjectReview } from '../api';
import { mockApi } from '../test/mockApi';
import { ProjectReviewSide } from './ProjectReviewSide';
import { SurveyorScreen } from './SurveyorScreen';

const projectId = project.id;
const reviewPath = `GET /api/projects/${projectId}/review`;
function nth<T>(xs: readonly T[], i: number): T {
  const x = xs[i];
  if (x === undefined) throw new Error(`no item ${String(i)}`);
  return x;
}
const current = nth(projectReview.drawings, 1); // plans/flat-b.pdf, 2 to review
const conflict = nth(projectReview.conflicts, 0);

afterEach(cleanup);

function renderSide() {
  return render(<ProjectReviewSide projectId={projectId} drawingId={current.drawing_id} />);
}

describe('ProjectReviewSide', () => {
  it('SV-41 lists every drawing with its review counts, marks the current one and links to its surveyor route', async () => {
    mockApi({ [reviewPath]: projectReview });
    renderSide();
    const list = await screen.findByRole('list', { name: /Drawings/ });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(projectReview.drawings.length);
    projectReview.drawings.forEach((d, i) => {
      const item = nth(items, i);
      const text = item.textContent;
      expect(text).toContain(d.file);
      expect(text.includes(`${String(d.to_review)} to review`)).toBe(d.to_review > 0);
      if (d.quantities === 0) expect(text).toContain('nothing counted');
      else expect(text).toContain(`${String(d.signed)} of ${String(d.quantities)} signed off`);
      expect(text.includes('current')).toBe(d.drawing_id === current.drawing_id);
      const link = within(item).getByRole('link');
      expect(link.getAttribute('href')).toBe(`#/p/${projectId}/d/${d.drawing_id}/surveyor`);
    });
    const currentLink = within(nth(items, 1)).getByRole('link');
    expect(currentLink.getAttribute('aria-current')).toBe('page');
  });

  it('SV-42 lists every conflict with label, file, values, its state, and a link to the quantity', async () => {
    const settled: ProjectReview = {
      ...projectReview,
      conflicts: [
        conflict,
        { ...conflict, quantity: 'door', label: 'door count', needs_person: true },
        {
          ...conflict,
          quantity: 'window',
          label: 'window count',
          settled: { value: 22.401, at: '2026-11-14T01:30:00Z' },
        },
      ],
    };
    mockApi({ [reviewPath]: settled });
    renderSide();
    const list = await screen.findByRole('list', { name: /Conflicts/ });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    const first = nth(items, 0).textContent;
    expect(first).toContain('area of room (name 1.01)');
    expect(first).toContain('plans/flat-b.pdf');
    expect(first).toContain('22.40 m² vs 30.00 m²');
    expect(first).toContain('decided by rule');
    expect(nth(items, 1).textContent).toContain('needs you');
    expect(nth(items, 2).textContent).toContain('settled');
    const href = within(nth(items, 0)).getByRole('link').getAttribute('href') ?? '';
    expect(href.startsWith(`#/p/${projectId}/d/${conflict.drawing_id}/surveyor?`)).toBe(true);
    expect(new URLSearchParams(href.split('?')[1]).get('q')).toBe('area:room|name=1.01');
  });

  it('SV-43 a failing review request shows detail, code and Retry in the side panel only', async () => {
    let fail = true;
    const api = mockApi({
      [`GET /api/drawings/${current.drawing_id}/takeoff`]: takeoff,
      [`GET /api/drawings/${current.drawing_id}`]: drawing,
      [reviewPath]: () =>
        fail
          ? { status: 500, body: { ...errorBody, detail: 'internal error', code: 'internal' } }
          : projectReview,
    });
    render(
      <SurveyorScreen
        projectId={projectId}
        drawingId={current.drawing_id}
        query={new URLSearchParams()}
      />,
    );
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('internal error');
    expect(alert.textContent).toContain('internal');
    expect(await screen.findByRole('table', { name: 'To review' })).toBeTruthy();
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await screen.findByRole('list', { name: /Drawings/ });
    expect(api.calls.filter((c) => c.url.includes('/review'))).toHaveLength(2);
  });

  it('SV-46 file names and labels from the project review render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    const body: ProjectReview = {
      drawings: [{ ...current, file: evil }],
      conflicts: [{ ...conflict, file: evil, label: evil }],
    };
    mockApi({ [reviewPath]: body });
    const { container } = renderSide();
    await screen.findByRole('list', { name: /Conflicts/ });
    expect(screen.getAllByText(evil, { exact: false }).length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('img')).toBeNull();
  });

  it('shows a loading line until the review answers', async () => {
    mockApi({ [reviewPath]: projectReview });
    renderSide();
    expect(screen.getByRole('status').textContent).toBe('Loading drawings…');
    await waitFor(() => {
      expect(screen.queryByRole('status')).toBeNull();
    });
  });
});
