// model-3d.md "More places" 1: "View in 3D" in the agent chat's plan pane (M3-21); scene and viewer mocked.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Highlight, ProjectAnswer } from '../api';
import { projectAsk } from '../api/fixtures';
import { PlanPane, PlanSheet } from '../agent/PlanPane';
import { flush } from '../ingest/testing';
import { mockApi } from '../test/mockApi';
import { paneHighlight } from './model3d';

const scene = vi.hoisted(() => ({
  rotate: vi.fn(),
  zoom: vi.fn(),
  reset: vi.fn(),
  dispose: vi.fn(),
  shown: { counts: { affected: 1 }, missing: 0, box: null },
}));
const mount = vi.hoisted(() => vi.fn());
vi.mock('./scene', () => ({ mount }));
vi.mock('../viewer/PageViewer', () => ({ PageViewer: () => <div data-testid="viewer" /> }));

type Part = ProjectAnswer['parts'][number];
const PID = 'p1';
const D = 'd326e2f2d0c40f6d';
const DOOR: Highlight = { global_id: '0000000000000000000002', role: 'affected' };
const WALL: Highlight = { global_id: '0000000000000000000004', role: 'affected' };
const [part] = projectAsk.parts as [Part];
const answerOn = (drawing_id: string, highlight?: Highlight[], refused = false): ProjectAnswer => ({
  ...projectAsk,
  parts: [
    {
      ...part,
      drawing_id,
      ...(highlight ? { highlight } : {}),
      answer: { ...part.answer, refusal: refused ? { ...(part.answer.refusal ?? {}) } : null },
    } as Part,
  ],
});

beforeEach(() => {
  mount.mockReset().mockResolvedValue(scene);
  scene.dispose.mockReset();
});
afterEach(cleanup);

describe('paneHighlight', () => {
  it('M3-21 the newest answered part for the drawing gives its highlight; else []', () => {
    const turns = [
      { answers: [answerOn(D, [WALL])] },
      { answers: [answerOn(D, [DOOR])] },
      { answers: [answerOn('other', [WALL])] },
      { answers: [answerOn(D, [WALL], true)] }, // refused: not shown, so not highlighted
    ];
    expect(paneHighlight(turns, D)).toEqual([DOOR]);
    expect(paneHighlight(turns, 'other')).toEqual([WALL]);
    expect(paneHighlight(turns, 'none')).toEqual([]);
    expect(paneHighlight([{ answers: [answerOn(D)] }], D)).toEqual([]);
  });
});

describe('the plan pane', () => {
  const pane = (model: { fileId: string; highlight: Highlight[] } | null) => (
    <PlanPane
      projectId={PID}
      files={[{ drawing_id: D, label: 'Building model 1', model, drawable: false }]}
      open={[D]}
      drawn={null}
      view={null}
      focus={null}
      reveal={null}
      drawMode={false}
      onToggle={vi.fn()}
      onPick={vi.fn()}
    />
  );

  it('M3-21 "View in 3D" only with a model; it opens the dialog with the highlight', async () => {
    render(pane(null));
    expect(screen.queryByRole('button', { name: /in 3D/ })).toBeNull();
    cleanup();
    const api = mockApi({ [`GET /api/projects/${PID}/files/f1/model.glb`]: 'glTF' });
    render(pane({ fileId: 'f1', highlight: [DOOR] }));
    const head = screen.getByRole('complementary', { name: 'Plan' });
    fireEvent.click(within(head).getByRole('button', { name: 'View in 3D: Building model 1' }));
    await flush();
    expect(screen.getByRole('dialog', { name: '3D view: Building model 1' })).toBeTruthy();
    expect(api.calls.map((c) => c.url)).toEqual([`/api/projects/${PID}/files/f1/model.glb`]);
    expect(mount.mock.calls[0]?.[2]).toEqual([DOOR]);
  });

  it('M3-21 Esc and Tab in the dialog stay in the dialog: the plan sheet around it stays open', async () => {
    mockApi({ [`GET /api/projects/${PID}/files/f1/model.glb`]: 'glTF' });
    const onClose = vi.fn();
    render(<PlanSheet onClose={onClose}>{pane({ fileId: 'f1', highlight: [] })}</PlanSheet>);
    const open = screen.getByRole('button', { name: 'View in 3D: Building model 1' });
    fireEvent.click(open);
    await flush();
    const dialog = screen.getByRole('dialog', { name: '3D view: Building model 1' });
    const close = within(dialog).getByRole('button', { name: 'Close' });
    fireEvent.keyDown(close, { key: 'Tab' });
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(close, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /^3D view/ })).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(open);
  });
});
