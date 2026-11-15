// model-3d.md "More places" 2: "View in 3D" on Documents' issue cards (M3-24, M3-25); scene and figure mocked.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FileStatus, Highlight, Issue, IssueList, Model3d, ProjectView } from '../api';
import { project, projectIssues } from '../api/fixtures';
import { DocumentsScreen } from '../documents/DocumentsScreen';
import { flush, must } from '../ingest/testing';
import { mockApi } from '../test/mockApi';
import { issueModel } from './model3d';

const scene = vi.hoisted(() => ({
  rotate: vi.fn(),
  zoom: vi.fn(),
  reset: vi.fn(),
  dispose: vi.fn(),
  shown: { counts: { affected: 1 }, missing: 0, box: null },
}));
const mount = vi.hoisted(() => vi.fn());
vi.mock('./scene', () => ({ mount }));
vi.mock('../viewer/SourceFigure', () => ({
  SourceFigure: ({ label }: { label: string }) => <figure aria-label={label} />,
}));

const PID = project.id;
const READY: Model3d = { state: 'ready', reason: '', elements: 6 };
const DOOR: Highlight = { global_id: '19Mfen0Pf4kePiWD$g5Bal', role: 'affected' };
const [sheetFile, modelFile] = project.files as [FileStatus, FileStatus];
const files = (sheet3d: Model3d | null, model3d: Model3d | null): FileStatus[] => [
  { ...sheetFile, id: 'f1', model_3d: sheet3d },
  { ...modelFile, id: 'f2', kind: 'ifc', model_3d: model3d },
];
// a failed code check on the sheet f1, whose model is f2, with no picture to draw (page null)
const base = must(projectIssues.issues.find((i) => i.kind === 'set_aside'));
const check: Issue = {
  ...base,
  id: 'check-1',
  kind: 'code_check_failed',
  severity: 'fails_rule',
  drawing_id: null,
  drawing_name: 'Drawn plan 1',
  file_id: 'f1',
  page: null,
  box: null,
  model_file_id: 'f2',
  highlight: [DOOR],
};

describe('issueModel', () => {
  it('M3-24 model_file_id first, else the issue file; only a file that can show 3D', () => {
    expect(issueModel(check, files(null, READY))).toEqual({ fileId: 'f2', highlight: [DOOR] });
    const unavailable: Model3d = {
      state: 'unavailable',
      code: 'too_big',
      reason: '',
      elements: null,
    };
    expect(issueModel(check, files(null, unavailable))).toBeNull();
    expect(issueModel(check, files(null, null))).toBeNull();
    const own = { ...check, model_file_id: null, highlight: undefined };
    expect(issueModel(own, files(READY, null))).toEqual({ fileId: 'f1', highlight: [] });
    expect(issueModel({ ...own, file_id: null }, files(READY, READY))).toBeNull();
  });
});

describe('the issue card', () => {
  beforeEach(() => {
    mount.mockReset().mockResolvedValue(scene);
  });
  afterEach(cleanup);

  async function show(body: ProjectView) {
    const issues: IssueList = { ...projectIssues, issues: [check] };
    const api = mockApi({
      [`GET /api/projects/${PID}`]: body,
      [`GET /api/projects/${PID}/issues`]: issues,
      [`GET /api/projects/${PID}/files/f2/model.glb`]: 'glTF',
    });
    render(<DocumentsScreen projectId={PID} pack={null} />);
    await flush();
    return api;
  }
  const card = () =>
    within(screen.getByRole('region', { name: 'Issues on demand' })).getAllByRole('listitem')[0];

  it('M3-25 "View in 3D" opens the model with the checked door; Esc closes, focus back', async () => {
    const api = await show({ ...project, files: files(null, READY) });
    const open = within(must(card())).getByRole('button', { name: 'View in 3D: Drawn plan 1' });
    expect(open.textContent).toBe('View in 3D');
    fireEvent.click(open);
    await flush();
    const dialog = screen.getByRole('dialog', { name: '3D view: Drawn plan 1' });
    expect(api.calls.some((c) => c.url === `/api/projects/${PID}/files/f2/model.glb`)).toBe(true);
    expect(mount.mock.calls[0]?.[2]).toEqual([DOOR]);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /^3D view/ })).toBeNull();
    expect(document.activeElement).toBe(open);
  });

  it('M3-25 no button without a file that can show 3D', async () => {
    await show({ ...project, files: files(null, null) });
    expect(within(must(card())).queryByRole('button', { name: /in 3D/ })).toBeNull();
  });
});
