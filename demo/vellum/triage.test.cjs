// Run: node --test demo/vellum/*.test.cjs  (file triage and the issues list, through stoa.js on a tiny made-up fixture;
// the real Stoa data is never committed)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const I = require('./issues.js');

const reg = (kind) => ({ kind, has_floor_plan: kind === 'floor_plan', photo_of_sheet: false, scale_shown: 'none', quality: 'good', method: 'hand-picked example' });
const desc = (text, shows, seen) => ({ text, what_it_is: 'drawing', shows_building: shows, visible_text: seen, detail: `${text} More.` });
const set = (p, kind, d) => ({ path: p, size: '1 kB', kind: 'JPG scan', image: p, credit: 'c (PDM)', lane: null, role: 'not a floor plan', triage: { register: reg(kind), description: d } });
const EL = 'archive/e.jpg', PH = 'archive/p.jpg', CO = 'archive/c.jpg';

function load() {
  const window = {};
  window.window = window;
  window.VStoaData = {
    archive: 'site1_bldg1_floor1', source: 'swiss_dwellings', credit: 'All files: CC-BY-4.0. Credit: test.',
    files: [{ path: 'f.png', size: '1 kB', kind: 'PNG rendering', lane: 'Vision', role: 'source', image: 'f.png' }],
    questions: [{ question: 'How many doors are drawn on this floor plan?', answer: 12, unit: 'count', type: 'count' }],
    archive_files: [
      { path: 'archive/plan.jpg', size: '1 kB', kind: 'JPG scan', image: 'archive/plan.jpg', credit: 'c (PDM)', lane: 'Vision', role: 'source', plan: true },
      set(EL, 'elevation', desc('A two-storey house seen from the east.', true, 'EAST ELEVATION\nJONES RESIDENCE')),
      set(PH, 'photograph', desc('A photo of a sign on a wall.', false, 'Kloster')),
      set(CO, 'cover_or_text_sheet', desc('A title sheet.', true, 'PLAN\nsite1 bldg1 floor1')),
    ],
  };
  const ctx = vm.createContext({ window });
  for (const f of ['data.js', 'stoa.js', 'triage.js']) {
    const src = fs.readFileSync(path.join(__dirname, f), 'utf8').replace("typeof module !== 'undefined' && module.exports", 'false');
    vm.runInContext(src, ctx, { filename: f });
  }
  return { V: window.VData, T: window.VTriage };
}
const { V, T } = load();
const ctx = (over = {}) => ({ done: true, calls: {}, rap: {}, now: 0, project: T.projectOf(V), conflicts: {}, ...over });

test('the class follows the register; every non-plan is set aside and counted', () => {
  assert.equal([EL, PH, CO].map(T.classOf).join(), 'other_drawing,not_drawing,not_drawing');
  assert.equal(T.notPlans(V.FILES), 3);
  assert.equal(T.notPlansLine(3), '3 not floor plans: kept, not read');
  assert.equal(T.notPlansLine(1), '1 not a floor plan: kept, not read');
});

test('relevance is the rule: a printed match is related, a building alone unsure, else unrelated', () => {
  const p = T.projectOf(V);
  const co = T.relevanceOf(CO, p);
  assert.equal(co.verdict, 'related');  // "bldg" of the name is printed on it; "site", "floor", "plan" are drawing words
  assert.ok(co.matched_on.some((m) => m.includes('(the project name)')));
  assert.equal(T.relevanceOf(EL, p).verdict, 'unsure');
  assert.equal(T.issueOf(EL, ctx()).severity, 'needs_person');
  const ph = T.relevanceOf(PH, p);
  assert.equal(ph.verdict, 'unrelated');
  assert.match(ph.why, /no building, and no printed word matches/);
});

test('rows, calls and the call line', () => {
  assert.equal(T.rowLine(PH, ctx({ done: false })).pill, '– Not judged');
  assert.equal(T.rowLine(PH, ctx()).text, 'Not a floor plan: not a drawing · a photo');
  assert.equal(T.rowLine(EL, ctx()).tone, 'warn');
  const called = ctx({ calls: { [PH]: { verdict: 'related', by: 'Ana', at: 0 } } });
  assert.equal(T.rowLine(PH, called).pill, '✓ Related');
  assert.equal(T.callLine(PH, called, '10:05'), 'Related to this project: Ana\'s call, 10:05. The rule said: not related.');
  assert.equal(T.rapState(PH, { ...ctx({ rap: { [PH]: { by: 'Ana', at: 0 } } }), now: 2000 }), 'running');
});

test('issues: severity order, settled in place by a call, CSV with FileStatus ids and no formulas', () => {
  assert.equal(I.issuesOf(V, T, ctx({ done: false })).length, 0);
  const list = I.issuesOf(V, T, ctx());
  assert.equal(list.map((x) => `${x.severity}:${x.file}`).join(), `needs_person:${EL},note:${PH}`);
  const after = I.issuesOf(V, T, ctx({ calls: { [EL]: { verdict: 'related', by: 'Ana', at: 0 } } }));
  assert.equal(after.map((x) => `${x.n}:${x.id}:${x.state}`).join(), `1:${list[0].id}:settled,2:${list[1].id}:open`);
  const csv = I.csv(list);
  assert.equal(csv.split('\n')[0], I.CSV_COLUMNS.join(','));
  assert.match(csv, /,f2,/);
  assert.equal(I.csv([{ why: '=1+1', file: '@x' }]).split('\n')[1].split(',').filter(Boolean).join(), "'@x,'=1+1");
});

test('the chat\'s elevation question quotes the real description, else its summary', () => {
  const st = T.described('How many storeys does the building in the elevation have?', V.FILES);
  assert.equal(st.path, EL);
  assert.ok(st.matched && st.quote.includes('two-storey'));
  assert.equal(T.described('What does the facade show?', V.FILES).matched, false);
  assert.equal(T.described('How many doors are there?', V.FILES), null);
});
