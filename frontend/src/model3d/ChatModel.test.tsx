// model-3d.md part 2: "View in 3D" from the chat answer (M3-10..M3-12): one round "3D" button in the answer
// figure's header (ui-bugs 5), for the shown drawing's model, else the first part with one; scene and viewer mocked.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { drawingLabel, type Highlight, type Model3d, type ProjectAnswer } from '../api';
import { project, projectAsk } from '../api/fixtures';
import { ChatAnswer } from '../engineer/ChatAnswer';
import { flush } from '../ingest/testing';
import { mockApi } from '../test/mockApi';
import { stubResizeObserver } from '../test/resizeObserver';

const scene = vi.hoisted(() => ({
  rotate: vi.fn(),
  zoom: vi.fn(),
  reset: vi.fn(),
  dispose: vi.fn(),
  shown: { counts: {}, missing: 0 },
}));
const mount = vi.hoisted(() => vi.fn());
vi.mock('./scene', () => ({ mount }));
vi.mock('../viewer/PageViewer', () => ({ PageViewer: () => <div data-testid="viewer" /> }));

type Part = ProjectAnswer['parts'][number];
const PID = project.id;
const DOOR: Highlight = { global_id: '0000000000000000000002', role: 'affected' };
const READY: Model3d = { state: 'ready', reason: '', elements: 6 };
const [a, b, c] = projectAsk.parts as [Part, Part, Part];
// as ChatAnswer names a drawing (CH-40): its plain name in the project, else its file
const label = (p: Part) =>
  drawingLabel(project.drawings.find((d) => d.drawing_id === p.drawing_id) ?? { file: p.name });
const GLB = `GET /api/projects/${PID}/files/f8/model.glb`;

/** The answer; a part made by ifc() is an IFC drawing in the project (its own model, W3). */
function show(parts: Part[]) {
  const ask: ProjectAnswer = { ...projectAsk, parts };
  const models = new Set(parts.filter((p) => p.answer.pages.length === 0).map((p) => p.drawing_id));
  const drawings = project.drawings.map((d) =>
    models.has(d.drawing_id) ? { ...d, kind: 'ifc' as const } : d,
  );
  render(<ChatAnswer ask={ask} project={{ ...project, drawings }} projectId={PID} pack={null} />);
}
/** W3: the 3D button belongs to the SHOWN drawing: choose that part's reference first. */
const choose = (p: Part) => {
  fireEvent.click(
    within(screen.getByRole('list', { name: 'References' })).getByRole('button', {
      name: new RegExp(label(p)),
    }),
  );
};
const ifc = (p: Part, model_3d: Model3d = READY, highlight?: Highlight[]): Part => ({
  ...p,
  answer: { ...p.answer, pages: [] },
  model_file_id: 'f8',
  model_3d,
  ...(highlight ? { highlight } : {}),
});
// the answer figure ("Reference n of m"), whose header holds the one 3D button
const fig = () => within(screen.getByRole('figure', { name: /^Reference / }));

beforeEach(() => {
  mount.mockReset().mockResolvedValue(scene);
  stubResizeObserver(); // the 3D button's tooltip opens when focus comes back to it
  scene.dispose.mockReset();
});
afterEach(cleanup);

describe('3D view from the chat answer', () => {
  it('M3-10 W3: one "View in 3D" in the figure header, only while the shown drawing has a model; unavailable or none gets nothing', () => {
    show([ifc(a), b, c]); // b is shown first (it has a page) and has no model: no button
    expect(screen.queryAllByRole('button', { name: /in 3D/ })).toHaveLength(0);
    choose(a);
    expect(screen.getAllByRole('button', { name: /^View.* in 3D/ })).toHaveLength(1);
    const open = fig().getByRole('button', { name: `View in 3D: ${label(a)}` });
    expect(open.textContent).toBe('3D');
    expect(
      screen
        .queryByRole('list', { name: 'References' })
        ?.querySelector('button[aria-label*="in 3D"]') ?? null,
    ).toBeNull();
    cleanup();
    show([ifc(a), ifc(b)]); // two models: still one button, the shown one's (the first, as neither has a page)
    expect(screen.getAllByRole('button', { name: /^View.* in 3D/ })).toHaveLength(1);
    expect(fig().getByRole('button', { name: `View in 3D: ${label(a)}` })).toBeTruthy();
    cleanup();
    // a 2D drawing linked to the building's model: the button names the building model
    show([{ ...b, model_file_id: 'f8', model_3d: READY }]);
    expect(fig().getByRole('button', { name: 'View the building model in 3D' })).toBeTruthy();
    cleanup();
    show([ifc(a, { state: 'unavailable', code: 'too_big', reason: 'too big', elements: null }), b]);
    choose(a);
    expect(screen.queryAllByRole('button', { name: /in 3D/ })).toHaveLength(0);
    cleanup();
    show([b]);
    expect(screen.queryAllByRole('button', { name: /in 3D/ })).toHaveLength(0);
    for (const state of ['not_started', 'converting'] as const) {
      cleanup();
      show([ifc(a, { state, reason: '', elements: null })]);
      expect(fig().getByRole('button', { name: `View in 3D: ${label(a)}` })).toBeTruthy();
    }
  });

  it('M3-11 the dialog loads the model file, closes on Esc and Close, focus back, Tab kept inside', async () => {
    const api = mockApi({ [GLB]: 'glTF' });
    show([ifc(a), b]);
    choose(a);
    const open = fig().getByRole('button', { name: `View in 3D: ${label(a)}` });
    fireEvent.click(open);
    await flush();
    const dialog = screen.getByRole('dialog', { name: `3D view: ${label(a)}` });
    expect(api.calls.map((x) => x.url)).toEqual([`/api/projects/${PID}/files/f8/model.glb`]);
    const close = within(dialog).getByRole('button', { name: 'Close' });
    expect(document.activeElement).toBe(close);
    const reset = within(dialog).getByRole('button', { name: 'Reset view' });
    reset.focus();
    fireEvent.keyDown(reset, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(reset);
    // The focused button's tip is open: the first Escape closes the tip only, the next one the dialog.
    expect(screen.getByRole('tooltip').textContent).toContain('Reset view');
    fireEvent.keyDown(reset, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
    expect(screen.getByRole('dialog')).toBeTruthy();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(scene.dispose).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(open);
    fireEvent.click(open);
    await flush();
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(open);
  });

  it("M3-12 the part's highlight goes to the scene; none gives []", async () => {
    mockApi({ [GLB]: 'glTF' });
    show([ifc(a, READY, [DOOR]), ifc(b)]);
    fireEvent.click(fig().getByRole('button', { name: `View in 3D: ${label(a)}` }));
    await flush();
    expect(mount.mock.calls[0]?.[2]).toEqual([DOOR]);
    cleanup();
    show([ifc(a), b]);
    choose(a);
    fireEvent.click(fig().getByRole('button', { name: `View in 3D: ${label(a)}` }));
    await flush();
    expect(mount.mock.calls[1]?.[2]).toEqual([]);
  });
});
