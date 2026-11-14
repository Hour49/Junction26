import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { trace } from '../api/fixtures';
import type { FileTrace, Model3d } from '../api';
import { FileTraceScreen } from '../ingest/FileTraceScreen';
import { flush } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';

const scene = vi.hoisted(() => ({
  rotate: vi.fn(),
  zoom: vi.fn(),
  reset: vi.fn(),
  dispose: vi.fn(),
}));
const mount = vi.hoisted(() => vi.fn());
vi.mock('./scene', () => ({ mount }));

const PID = trace.project_id;
const FID = trace.file.id;
const TRACE = `GET /api/projects/${PID}/files/${FID}/trace`;
const GLB = `GET /api/projects/${PID}/files/${FID}/model.glb`;
const glbCalls = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.url.endsWith('/model.glb')).length;

const withModel = (model_3d: Model3d | null): FileTrace => ({
  ...trace,
  file: { ...trace.file, model_3d },
});
const READY: Model3d = { state: 'ready', reason: '', elements: 1234 };

async function open(glb: unknown, model: Model3d | null = READY) {
  const api = mockApi({ [TRACE]: withModel(model), [GLB]: glb });
  render(<FileTraceScreen projectId={PID} fileId={FID} />);
  await flush();
  return api;
}
async function press(name = 'Show in 3D') {
  fireEvent.click(screen.getByRole('button', { name }));
  await flush();
}

beforeEach(() => {
  mount.mockReset().mockResolvedValue(scene);
  for (const f of Object.values(scene)) f.mockReset();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('3D view on the file page', () => {
  it('M3-1 a file with model_3d shows the card and the element count; no GLB before the press', async () => {
    const api = await open('glTF');
    const card = screen.getByRole('region', { name: '3D view' });
    expect(card.textContent).toContain('1234 elements');
    expect(screen.getByRole('button', { name: 'Show in 3D' })).toBeTruthy();
    expect(glbCalls(api)).toBe(0);
  });

  it('M3-1 no model_3d: no card', async () => {
    await open('glTF', null);
    expect(screen.queryByRole('region', { name: '3D view' })).toBeNull();
    expect(screen.queryByText('Show in 3D')).toBeNull();
  });

  it('M3-2 unavailable: the reason, no button; not_started and converting keep the button', async () => {
    await open('glTF', {
      state: 'unavailable',
      reason: 'The model is too big for a 3D view (85 MB).',
      code: 'too_big',
      elements: null,
    });
    expect(
      screen.getByText('3D view unavailable: The model is too big for a 3D view (85 MB).'),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Show in 3D' })).toBeNull();
    cleanup();
    await open('glTF', { state: 'unavailable', reason: '', code: 'failed', elements: null });
    expect(screen.getByText('3D view unavailable: the model cannot be shown in 3D')).toBeTruthy();
    for (const state of ['not_started', 'converting'] as const) {
      cleanup();
      await open('glTF', { state, reason: '', elements: null });
      expect(screen.getByRole('button', { name: 'Show in 3D' })).toBeTruthy();
    }
  });

  it('M3-3 the press loads the GLB once, shows loading, then mounts the scene on a labelled canvas', async () => {
    let answer: (v: unknown) => void = () => undefined;
    const api = await open(new Promise((r) => (answer = r)));
    await press();
    expect(screen.getByText('Loading the 3D view…')).toBeTruthy();
    expect(api.calls.at(-1)?.url).toBe(`/api/projects/${PID}/files/${FID}/model.glb`);
    answer('glTF');
    await flush();
    expect(glbCalls(api)).toBe(1);
    expect(mount).toHaveBeenCalledOnce();
    const [canvas, bytes] = mount.mock.calls[0] as [HTMLCanvasElement, ArrayBuffer];
    expect(canvas).toBe(screen.getByRole('img', { name: `3D view of ${trace.file.path}` }));
    expect(new TextDecoder().decode(bytes)).toBe('glTF');
    expect(screen.queryByText('Loading the 3D view…')).toBeNull();
  });

  it('M3-4 409 converting: preparing, retried every 5 s at most 24 times, Try again at once', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    let n = 0;
    const api = await open(() =>
      ++n < 3 ? reply(409, { detail: 'converting', code: 'converting' }) : 'glTF',
    );
    await press();
    expect(screen.getByText('Preparing the 3D view…')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    await act(() => vi.advanceTimersByTimeAsync(5000));
    await flush();
    expect(glbCalls(api)).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await flush();
    expect(glbCalls(api)).toBe(3);
    expect(mount).toHaveBeenCalledOnce();
    expect(screen.queryByText('Preparing the 3D view…')).toBeNull();
  });

  it('M3-4 gives up after the 24th 409', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const api = await open(reply(409, { detail: 'converting', code: 'converting' }));
    await press();
    for (let i = 0; i < 30; i++) {
      await act(() => vi.advanceTimersByTimeAsync(5000));
      await flush(2);
    }
    expect(glbCalls(api)).toBe(24);
    expect(screen.getByText('Still preparing. Try again later.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await flush();
    expect(glbCalls(api)).toBe(25);
  });

  it('M3-5 422 and 404: unavailable with the reason, no retry', async () => {
    await open(reply(422, { detail: 'The model has no geometry.', code: 'no_geometry' }));
    await press();
    expect(screen.getByText('3D view unavailable: The model has no geometry.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    cleanup();
    await open(reply(404, { detail: 'not found', code: 'not-found' }));
    await press();
    expect(screen.getByText('3D view unavailable: no 3D model for this file')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
  });

  it('M3-6 500 or a scene that cannot mount: the reason with Try again', async () => {
    const api = await open(reply(500, { detail: 'boom', code: 'internal' }));
    await press();
    expect(screen.getByText('3D view unavailable: boom (internal)')).toBeTruthy();
    cleanup();
    mount.mockRejectedValueOnce(new Error('this browser cannot draw 3D'));
    const api2 = await open('glTF');
    await press();
    expect(screen.getByText('3D view unavailable: this browser cannot draw 3D')).toBeTruthy();
    await press('Try again');
    expect(glbCalls(api2)).toBe(2);
    expect(mount).toHaveBeenCalledTimes(2);
    expect(glbCalls(api)).toBe(1);
  });

  it('M3-7 the toolbar buttons call the scene, in tab order after the canvas; keys zoom', async () => {
    await open('glTF');
    await press();
    const names = ['Rotate left', 'Rotate right', 'Zoom in', 'Zoom out', 'Reset view'];
    const buttons = names.map((name) => screen.getByRole('button', { name }));
    const canvas = screen.getByRole('img', { name: /^3D view of/ });
    expect(canvas.tabIndex).toBe(0);
    for (const b of buttons) {
      expect(b.tagName).toBe('BUTTON');
      expect(canvas.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    buttons.forEach((b) => fireEvent.click(b));
    expect(scene.rotate.mock.calls).toEqual([[-15], [15]]);
    expect(scene.zoom.mock.calls).toEqual([[0.8], [1.25]]);
    expect(scene.reset).toHaveBeenCalledOnce();
    fireEvent.keyDown(canvas, { key: '+' });
    fireEvent.keyDown(canvas, { key: '-' });
    expect(scene.zoom.mock.calls.slice(2)).toEqual([[0.8], [1.25]]);
  });

  it('M3-8 unmount disposes the scene once and aborts a pending GLB request', async () => {
    await open('glTF');
    await press();
    cleanup();
    expect(scene.dispose).toHaveBeenCalledOnce();
    const api = await open(never());
    await press();
    const init = api.fetch.mock.calls.at(-1)?.[1];
    expect(init?.signal?.aborted).toBe(false);
    cleanup();
    expect(init?.signal?.aborted).toBe(true);
    expect(glbCalls(api)).toBe(1);
  });
});
