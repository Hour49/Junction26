// Hand-made fixtures in the #142 shapes (issues.md "Files owned"); replaced by Bogdan's when his PR lands.
import type { Issue, IssueList } from '../api';

export const PID = 'a8d435e09c5d';
export const DRAWING_B = '44cc9f0d991eafe3';
export const DRAWING_IFC = '1db9bcf1e67e27a3';

const base: Issue = {
  id: 'i-1',
  kind: 'conflict',
  severity: 'needs_person',
  state: 'open',
  drawing_id: DRAWING_B,
  file: 'plans/flat-b.pdf',
  file_id: 'f3',
  floor: '1',
  page: 1,
  box: [0.1, 0.2, 0.3, 0.4],
  polygon: null,
  why: 'The two methods read 22.40 m² and 30.00 m² for room 1.01.',
  mark_id: 'r1',
  quantity: 'area:room|name=1.01',
  question: null,
  reason: null,
  check: null,
  links: { drawing: null, takeoff: null, trace: null, checks: null },
};

/** API order (severity, drawing, page, box top); deliberately not alphabetical or by state. */
export const issues: Issue[] = [
  {
    ...base,
    id: 'i-check',
    kind: 'code_check_failed',
    severity: 'fails_rule',
    why: 'The door is 0.75 m wide; the rule asks for at least 0.80 m.',
    box: [0.5, 0.1, 0.55, 0.15],
    polygon: [
      [0.5, 0.1],
      [0.55, 0.1],
      [0.55, 0.15],
    ],
    quantity: 'door',
    check: 'fi:door-width:d2',
  },
  { ...base, id: 'i-conflict' },
  {
    ...base,
    id: 'i-refused',
    kind: 'refused_answer',
    drawing_id: null,
    file: 'sample-project.zip',
    floor: null,
    page: null,
    box: null,
    mark_id: null,
    quantity: null,
    question: 'How many saunas are there?',
    why: 'The question could not be answered from the drawings.',
  },
  {
    ...base,
    id: 'i-ifc',
    kind: 'reading_flag',
    state: 'settled',
    drawing_id: DRAWING_IFC,
    file: 'model/house.ifc',
    file_id: 'f8',
    floor: 'Ground floor',
    page: null,
    box: null,
    quantity: null,
    why: 'The model has no storey heights.',
  },
  {
    ...base,
    id: 'i-aside',
    kind: 'set_aside',
    severity: 'note',
    state: 'signed_off',
    drawing_id: null,
    file: 'photos/site.jpg',
    file_id: 'f7',
    floor: null,
    page: null,
    box: null,
    mark_id: null,
    quantity: null,
    why: 'A photo, not of a drawing.',
    reason: 'a photo, not of a drawing (1600x1200 px)',
  },
];

export const issueList: IssueList = { project_id: PID, pack: null, issues };
export const issueListFi: IssueList = { ...issueList, pack: 'fi' };
