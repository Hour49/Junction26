import { describe, expect, it } from 'vitest';
import { project, projectChecks, projectIssues, projectReview, takeoff } from '../api/fixtures';
import type { ProjectView } from '../api';
import { COLUMNS, fileName, roomLabel, scanRows, toCsv, type Scan } from './csv';

// extraction_v1 has no contract fixture (getModel is untyped): a minimal model in its shape (decision 0004).
const model = {
  rooms: [
    {
      id: 'r1',
      type: 'kitchen',
      label: 'Küche',
      page: 1,
      area_m2: 22.401,
      area_status: 'measured',
      attrs: { number: '1.03' },
    },
  ],
  elements: [
    { id: 'e1', class: 'door', page: 1, box: [0, 0, 1, 1] },
    { id: 'e2', class: 'window', page: 1, box: [0, 0, 1, 1] },
  ],
  model_objects: [
    { id: 'o1', class: 'door', element: 'e1', quantities: { width_m: 0.9, height_m: 2.1 } },
  ],
};

const scan: Scan = {
  project,
  review: projectReview,
  issues: projectIssues,
  checks: projectChecks,
  drawings: [{ drawing_id: takeoff.drawing_id, file: takeoff.file, takeoff, model }],
};

const lines = (csv: string) =>
  csv
    .replace(/^\uFEFF/, '')
    .split('\r\n')
    .filter(Boolean);
const HEADER =
  'kind,file,drawing_id,page,item,type,label,value,unit,width_m,height_m,status,detail';

describe('scan CSV', () => {
  it('EX-4 a set-aside file the project lists in both files and skipped is one row (QA fe-ui2)', () => {
    const [aside, lost] = [project.skipped[0], project.skipped[1]];
    if (!aside || !lost) throw new Error('project.json has two skipped files');
    const file = project.files[0];
    if (!file) throw new Error('project.json has a file');
    // the backend lists a set-aside file under files (with its id) and again under skipped
    const both: ProjectView = {
      ...project,
      files: [
        ...project.files,
        { ...file, id: 'f9', path: aside.path, state: 'set_aside', reason: aside.reason },
      ],
    };
    const rows = scanRows({ ...scan, project: both }).filter((r) => r.kind === 'file');
    expect(rows.filter((r) => r.file === aside.path).map((r) => [r.item, r.status])).toEqual([
      ['f9', 'set_aside'],
    ]);
    // a skipped file that never became a file (the server restarted mid-ingest) keeps its row
    expect(rows.filter((r) => r.file === lost.path).map((r) => r.status)).toEqual(['skipped']);
  });

  it('EX-3 the first line is the header', () => {
    expect(COLUMNS.join(',')).toBe(HEADER);
    expect(lines(toCsv(scanRows(scan)))[0]).toBe(HEADER);
  });

  it('EX-4 one row per item of each kind', () => {
    const rows = scanRows(scan);
    const count = (kind: string) => rows.filter((r) => r.kind === kind).length;
    expect(count('file')).toBe(project.files.length + project.skipped.length);
    expect(count('room')).toBe(1);
    expect(count('element')).toBe(2);
    expect(count('quantity')).toBe(takeoff.quantities.length);
    expect(count('conflict')).toBe(projectReview.conflicts.length);
    const results = projectChecks.drawings.flatMap((d) => d.rules.flatMap((r) => r.results));
    expect(count('check')).toBe(results.length);
    expect(count('issue')).toBe(projectIssues.issues.length);
    const door = rows.find((r) => r.item === 'e1');
    expect(door).toMatchObject({ type: 'door', width_m: 0.9, height_m: 2.1, file: takeoff.file });
    expect(rows.find((r) => r.item === 'e2')?.width_m).toBeUndefined();
    expect(rows.find((r) => r.kind === 'room')).toMatchObject({
      type: 'kitchen',
      label: 'Küche 1.03',
      value: 22.4,
      unit: 'm2',
    });
    const conflict = rows.find((r) => r.kind === 'conflict');
    expect(conflict?.status).toBe('settled by rule');
    expect(conflict?.detail).toContain('22.401');
    // QA R2-E9: method ids in words, as the conflict card names them
    expect(conflict?.detail).not.toMatch(/polygon_x_scale|printed_label/);
    expect(conflict?.detail).toContain('room outlines × sheet scale 22.401 m2');
    expect(scanRows({ ...scan, checks: null }).some((r) => r.kind === 'check')).toBe(false);
  });

  it('EX-5 RFC 4180 quoting and CRLF line ends', () => {
    const csv = toCsv([{ kind: 'file', label: 'a,b', detail: 'say "hi"\nthere', item: 'x\ry' }]);
    const body = csv.replace(/^\uFEFF/, '');
    expect(body.endsWith('\r\n')).toBe(true);
    expect(body.split('\r\n')[1]).toMatch(/^file,,,,"x\ry",/);
    expect(body).toContain(',"a,b",');
    expect(body).toContain(',"say ""hi""\nthere"\r\n');
  });

  it('EX-6 starts with a UTF-8 BOM and keeps umlauts', () => {
    const csv = toCsv([{ kind: 'room', label: 'Küche äö' }]);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv).toContain('Küche äö');
  });

  it('EX-7 text cells starting with = + - @ tab or CR get a leading quote', () => {
    const csv = toCsv([
      { kind: 'issue', label: '=SUM(A1)', detail: '+1', item: '-x', type: '@a', status: '\tz' },
    ]);
    expect(lines(csv)[1]).toBe("issue,,,,'-x,'@a,'=SUM(A1),,,,,'\tz,'+1");
  });

  it('EX-8 numbers stay numbers', () => {
    const csv = toCsv([{ kind: 'quantity', value: -3, width_m: 22.401, page: 1 }]);
    expect(lines(csv)[1]).toBe('quantity,,,1,,,,-3,,22.401,,,');
  });

  it('EX-9 an empty project gives a header-only file', () => {
    const empty: ProjectView = { ...project, files: [], drawings: [], skipped: [] };
    const csv = toCsv(
      scanRows({
        project: empty,
        review: { drawings: [], conflicts: [] },
        issues: { ...projectIssues, issues: [] },
        checks: null,
        drawings: [],
      }),
    );
    expect(csv).toBe(`\uFEFF${HEADER}\r\n`);
  });

  it('EX-2 file name: project name without .zip, unsafe characters replaced, local date', () => {
    const date = new Date(2026, 10, 4, 23, 30);
    expect(fileName('sample-project.zip', date)).toBe('sample-project-scan-2026-11-04.csv');
    expect(fileName('a/b:c?.ZIP', date)).toBe('a-b-c--scan-2026-11-04.csv');
  });
});

describe('R3-L3 room rows', () => {
  it('the printed number goes with the name, once; no number keeps the name', () => {
    expect(roomLabel('Stanza', '1.07')).toBe('Stanza 1.07');
    expect(roomLabel('Room 1.07', '1.07')).toBe('Room 1.07');
    expect(roomLabel('Stanza', null)).toBe('Stanza');
    expect(roomLabel(null, '1.07')).toBe('1.07');
    expect(roomLabel(undefined, ' ')).toBeNull();
  });
});
