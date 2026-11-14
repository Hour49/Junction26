// model-3d.md part 2: "View in 3D" from the chat's References (M3-10..M3-12); the scene and the viewer mocked.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { drawingLabel, type Highlight, type Model3d, type ProjectAnswer } from '../api';
import { project, projectAsk } from '../api/fixtures';
import { ChatAnswer } from '../engineer/ChatAnswer';
import { flush } from '../ingest/testing';
import { mockApi } from '../test/mockApi';

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

function show(parts: Part[]) {
  const ask: ProjectAnswer = { ...projectAsk, parts };
  render(<ChatAnswer ask={ask} project={project} projectId={PID} pack={null} />);
}
const ifc = (p: Part, model_3d: Model3d = READY, highlight?: Highlight[]): Part => ({
  ...p,
  answer: { ...p.answer, pages: [] },
  model_file_id: 'f8',
  model_3d,
  ...(highlight ? { highlight } : {}),
});
const refs = () => within(screen.getByRole('list', { name: 'References' }));

beforeEach(() => {
  mount.mockReset().mockResolvedValue(scene);
  scene.dispose.mockReset();
});
afterEach(cleanup);

describe('3D view from the chat References', () => {
  it('M3-10 a part with a 3D model gets "View in 3D"; unavailable or none gets nothing', () => {
    show([ifc(a), b, c]); // c is refused: never a reference
    expect(refs().getAllByRole('button', { name: /in 3D/ })).toHaveLength(1);
    expect(refs().getByRole('button', { name: `View in 3D: ${label(a)}` })).toBeTruthy();
    expect(refs().getAllByRole('listitem')).toHaveLength(2);
    cleanup();
    show([ifc(a, { state: 'unavailable', code: 'too_big', reason: 'too big', elements: null }), b]);
    expect(refs().queryAllByRole('button', { name: /in 3D/ })).toHaveLength(0);
    for (const state of ['not_started', 'converting'] as const) {
      cleanup();
      show([ifc(a, { state, reason: '', elements: null })]);
      expect(refs().getByRole('button', { name: `View in 3D: ${label(a)}` })).toBeTruthy();
    }
  });

  it('M3-11 the dialog loads the model file, closes on Esc and Close, focus back, Tab kept inside', async () => {
    const api = mockApi({ [GLB]: 'glTF' });
    show([ifc(a), b]);
    const open = refs().getByRole('button', { name: `View in 3D: ${label(a)}` });
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
    fireEvent.click(refs().getByRole('button', { name: `View in 3D: ${label(a)}` }));
    await flush();
    expect(mount.mock.calls[0]?.[2]).toEqual([DOOR]);
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    fireEvent.click(refs().getByRole('button', { name: `View in 3D: ${label(b)}` }));
    await flush();
    expect(mount.mock.calls[1]?.[2]).toEqual([]);
  });
});
