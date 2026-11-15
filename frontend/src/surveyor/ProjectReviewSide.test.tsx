import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, error as errorBody, project, projectReview, takeoff } from '../api/fixtures';
import { drawingLabel, type ProjectReview } from '../api';
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
  it('K3 one toggle with both counts folds the lists away (on a phone CSS hides them while folded)', async () => {
    mockApi({ [reviewPath]: projectReview });
    const { container } = renderSide();
    const toggle = await screen.findByRole('button', {
      name: `Drawings (${String(projectReview.drawings.length)}) · Conflicts (${String(projectReview.conflicts.length)})`,
    });
    const side = container.querySelector('.sv-side');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(side?.getAttribute('data-open')).toBe('false');
    const body = container.querySelector('.sv-side-body');
    expect(body?.id).toBeTruthy();
    expect(toggle.getAttribute('aria-controls')).toBe(body?.id);
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(side?.getAttribute('data-open')).toBe('true');
    // the lists stay in the page either way: wider screens show them always (no media query in jsdom)
    expect(within(body as HTMLElement).getByRole('list', { name: /Drawings/ })).toBeTruthy();
  });

  it('SV-41 lists every drawing with its review counts, marks the current one and links to its surveyor route', async () => {
    mockApi({ [reviewPath]: projectReview });
    renderSide();
    const list = await screen.findByRole('list', { name: /Drawings/ });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(projectReview.drawings.length);
    projectReview.drawings.forEach((d, i) => {
      const item = nth(items, i);
      const text = item.textContent;
      expect(text).toContain(drawingLabel(d)); // no names passed: the file name (SV-56)
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
    expect(first).toContain('area of room (name Küche · 1.01)');
    expect(first).toContain('flat-b.pdf'); // no names passed: drawingLabel's file name (SV-56)
    expect(first).toContain('22.40 m² vs 30.00 m²');
    expect(first).toContain('settled by a rule'); // the project page card's words (R4-B11)
    expect(nth(items, 1).textContent).toContain('needs you');
    expect(nth(items, 2).textContent).toContain('settled by you');
    const href = within(nth(items, 0)).getByRole('link').getAttribute('href') ?? '';
    expect(href.startsWith(`#/p/${projectId}/d/${conflict.drawing_id}/surveyor?`)).toBe(true);
    expect(new URLSearchParams(href.split('?')[1]).get('q')).toBe('area:room|name=1.01');
  });

  it('SV-43 a failing review request shows detail, code and Retry in the side panel only', async () => {
    let fail = true;
    const api = mockApi({
      [`GET /api/drawings/${current.drawing_id}/takeoff`]: takeoff,
      [`GET /api/drawings/${current.drawing_id}`]: drawing,
      [`GET /api/projects/${projectId}`]: project,
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

  it("SV-56 with the project's names the drawings and the conflicts name each drawing plainly (#224)", async () => {
    mockApi({ [reviewPath]: projectReview });
    const names = Object.fromEntries(project.drawings.map((d) => [d.drawing_id, drawingLabel(d)]));
    render(
      <ProjectReviewSide projectId={projectId} drawingId={current.drawing_id} names={names} />,
    );
    const list = await screen.findByRole('list', { name: /Drawings/ });
    expect(
      within(list)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(projectReview.drawings.map((d) => names[d.drawing_id]));
    const conflicts = screen.getByRole('list', { name: /Conflicts/ });
    expect(conflicts.textContent).toContain('Drawn plan 2');
    expect(conflicts.textContent).not.toContain('plans/flat-b.pdf');
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

  it('R4-B9 R4-B5 the conflicts link lands on the first card that needs you; it says Settle only when one does', async () => {
    const needs = { ...conflict, quantity: 'door', label: 'door count', needs_person: true };
    mockApi({ [reviewPath]: { ...projectReview, conflicts: [conflict, needs] } });
    renderSide();
    const link = await screen.findByRole('link', { name: 'Settle the conflicts' });
    const [path, query] = (link.getAttribute('href') ?? '').split('?');
    expect(path).toBe(`#/p/${projectId}`);
    const q = new URLSearchParams(query);
    expect([q.get('d'), q.get('q')]).toEqual([needs.drawing_id, 'door']);
    cleanup();
    mockApi({ [reviewPath]: { ...projectReview, conflicts: [conflict] } }); // decided by a rule only
    renderSide();
    const see = await screen.findByRole('link', { name: 'See the conflicts' });
    expect(new URLSearchParams(see.getAttribute('href')?.split('?')[1]).get('q')).toBe(
      conflict.quantity,
    );
    expect(screen.queryByRole('link', { name: 'Settle the conflicts' })).toBeNull();
  });
});
