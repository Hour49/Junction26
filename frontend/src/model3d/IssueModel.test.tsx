// model-3d.md "More places" 2: which model an issue shows (M3-24). The issue card's "View in 3D" (M3-25) was
// tested through the Documents screen, which no longer lists issues (P6a); the card moves to the chat.
import { describe, expect, it } from 'vitest';
import type { FileStatus, Highlight, Issue, Model3d } from '../api';
import { project, projectIssues } from '../api/fixtures';
import { must } from '../ingest/testing';
import { issueModel } from './model3d';

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
