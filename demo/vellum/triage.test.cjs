// Run: node --test demo/vellum/  (file triage preview and the issues list, on the synthetic sample)
const test = require('node:test');
const assert = require('node:assert/strict');
const V = require('./data.js');
const T = require('./triage.js');
const I = require('./issues.js');

const ctx = (over = {}) => ({ done: true, calls: {}, rap: {}, now: 0, project: T.projectOf(V),
  conflicts: Object.fromEntries(V.CONFLICTS.map((c) => [c.id, { mode: c.ai === null ? 'open' : 'ai' }])), ...over });
const TRIAGED = ['elevations/south-elevation.png', 'photos/site.jpg', 'misc/poster.jpg', 'scans/annex-sketch.jpg'];

test('the class follows the register, and every triaged file of the sample is set aside', () => {
  assert.deepEqual(TRIAGED.map(T.classOf), ['other_drawing', 'not_drawing', 'not_drawing', 'other_drawing']);
  for (const p of TRIAGED) assert.equal(V.FILES.find((f) => f.path === p).drawing, null);
  assert.equal(T.notPlans(V.FILES, ctx()), 4);
  assert.equal(T.notPlansLine(4), '4 not floor plans: kept, not read');
  assert.equal(T.notPlansLine(1), '1 not a floor plan: kept, not read');
  assert.equal(T.notPlansLine(0), 'No image set aside as not a floor plan');
});

test('relevance is the rule: a building shown, or a printed word matching the project; why names the match', () => {
  const p = T.projectOf(V);
  const elev = T.relevanceOf('elevations/south-elevation.png', p);
  assert.equal(elev.verdict, 'related');
  assert.ok(elev.matched_on.some((m) => m.includes('"Harbour" (the project name)')));
  assert.equal(T.relevanceOf('scans/annex-sketch.jpg', p).verdict, 'related');
  assert.ok(T.relevanceOf('scans/annex-sketch.jpg', p).matched_on.some((m) => m.includes('"Kitchen" (the text on the plans)')));
  for (const path of ['photos/site.jpg', 'misc/poster.jpg']) {
    const r = T.relevanceOf(path, p);
    assert.equal(r.verdict, 'unrelated');
    assert.match(r.why, /no building, and no printed word matches/);
    assert.match(r.judge, /^rule: /);
  }
});

test('a building with no printed match is unsure, so its issue needs a person (#152 c6877132244)', () => {
  const bare = { name: 'other-project.zip', paths: [], plan: '' };
  const r = T.relevanceOf('elevations/south-elevation.png', bare);
  assert.equal(r.verdict, 'unsure');
  assert.match(r.why, /^unsure: it shows a building, but no printed word matches/);
  assert.equal(T.issueOf('elevations/south-elevation.png', ctx({ project: bare })).severity, 'needs_person');
  assert.equal(T.relevanceOf('photos/site.jpg', bare).verdict, 'unrelated');
});

test('rows say not judged until the project is read, then the verdict, then the call; the call line names the rule', () => {
  assert.equal(T.rowLine('photos/site.jpg', ctx({ done: false })).pill, '– Not judged');
  assert.equal(T.rowLine('photos/site.jpg', ctx()).text, 'Not a floor plan: not a drawing · photograph');
  assert.equal(T.rowLine('photos/site.jpg', ctx()).pill, '✕ Not related');
  const called = ctx({ calls: { 'photos/site.jpg': { verdict: 'related', by: 'Ana', at: 0 } } });
  assert.deepEqual(T.rowLine('photos/site.jpg', called), { text: 'Not a floor plan: not a drawing · photograph', pill: '✓ Related', by: 'Ana' });
  assert.equal(T.callLine('photos/site.jpg', called, '10:05'), 'Related to this project: Ana\'s call, 10:05. The rule said: not related.');
});

test('read as a floor plan: the annex sketch becomes drawing 7 once its re-read is ready, and leaves not_plans', () => {
  const path = 'scans/annex-sketch.jpg', c = ctx({ rap: { [path]: { by: 'Ana', at: 0 } } });
  assert.equal(T.rapState(path, { ...c, now: 500 }), 'queued');
  assert.equal(T.rapState(path, { ...c, now: 2000 }), 'running');
  assert.equal(T.rapState(path, { ...c, now: 3000 }), 'ready');
  assert.equal(T.notPlans(V.FILES, c), 3);
  const n = V.DRAWINGS.length;
  try {
    const d = V.readAsPlan(path);
    assert.equal(V.readAsPlan(path), d);  // idempotent
    assert.equal(V.DRAWINGS.length, n + 1);
    assert.equal(V.FILES.find((f) => f.path === path).drawing, 'annex');
    assert.equal(V.answer('annex', 'How many doors?', {}).value, 2);
    assert.equal(V.readAsPlan('photos/site.jpg'), null);  // no layout: the reading finds nothing
    assert.equal(T.rowLine(path, { ...c, now: 3000 }, true).text, 'Read as a floor plan on Ana\'s call');
    assert.equal(T.rowLine('photos/site.jpg', { ...c, rap: { 'photos/site.jpg': { by: 'Ana', at: 0 } }, now: 3000 }, false).text,
      'read as a floor plan: no rooms or openings were found on it');
  } finally { V.resetReadAsPlan(); }
  assert.equal(V.DRAWINGS.length, n);
  assert.equal(V.FILES.find((f) => f.path === path).drawing, null);
});

test('issues: kinds, severity order, nothing before the reading ends', () => {
  assert.deepEqual(I.issuesOf(V, T, ctx({ done: false })), []);
  const list = I.issuesOf(V, T, ctx());
  assert.deepEqual(list.map((x) => [x.kind, x.severity, x.state]), [
    ['conflict', 'needs_person', 'open'],  // c3, the open one
    ['conflict', 'note', 'settled'], ['conflict', 'note', 'settled'],
    ['unrelated_file', 'note', 'open'], ['unrelated_file', 'note', 'open'],  // site.jpg, poster.jpg
    ['set_aside', 'note', 'open'], ['set_aside', 'note', 'open'],  // readme.txt, __MACOSX
  ]);
  assert.deepEqual(list.map((x) => x.n), [1, 2, 3, 4, 5, 6, 7]);
  assert.equal(I.countsLine(list), '5 open · 2 settled');
  assert.equal(list.find((x) => x.kind === 'set_aside').why, 'Set aside at ingest: not a drawing.');
});

test('a call settles the unrelated_file issue in place; read as a plan adds one; CSV has the API columns', () => {
  const before = I.issuesOf(V, T, ctx()).find((x) => x.file === 'photos/site.jpg');
  const after = I.issuesOf(V, T, ctx({ calls: { 'photos/site.jpg': { verdict: 'related', by: 'Ana', at: 0 } } })).find((x) => x.file === 'photos/site.jpg');
  assert.equal(after.id, before.id);
  assert.equal(after.n, before.n);
  assert.equal(after.state, 'settled');
  assert.match(after.why, /Ana says it is related\.$/);
  const read = I.issuesOf(V, T, ctx({ rap: { 'scans/annex-sketch.jpg': { by: 'Ana', at: 0 } } })).find((x) => x.file === 'scans/annex-sketch.jpg');
  assert.equal(read.state, 'settled');
  assert.match(read.why, /Ana had it read as a floor plan\.$/);
  const csv = I.csv(I.issuesOf(V, T, ctx()));
  assert.equal(csv.split('\n')[0], I.CSV_COLUMNS.join(','));
  assert.equal(csv.trim().split('\n').length, 8);
  assert.ok(csv.includes('"Set aside at ingest: a system file, skipped."'));  // a comma inside is quoted
});

test('the chat\'s elevation question quotes the description\'s sentences holding its words, else the summary', () => {
  const files = V.FILES;
  const st = T.described('How many storeys does the building in the elevation have?', files);
  assert.equal(st.path, 'elevations/south-elevation.png');
  assert.ok(st.matched && st.quote.includes('four-storey'));
  const f = T.described('What does the facade show?', files);
  assert.equal(f.matched, false);
  assert.equal(f.quote, T.of(f.path).description.text);
  assert.equal(T.described('How many doors are there?', files), null);
});

test('the chat\'s data follow-ups all answer on the sample (chat.js FOLLOW)', () => {
  for (const q of ['How many rooms are there?', 'What is the net floor area?', 'What is the area of the living room?']) {
    assert.ok(V.askProject(q, {}).parts.some((p) => !p.answer.refusal), q);
  }
});
