// Run: node --test demo/vellum/  (Stoa mode with a tiny made-up fixture; the real Stoa data is never committed)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(archiveFiles) {
  const window = {};
  window.window = window;
  window.VStoaData = {
    archive: 'site1_bldg1_floor1', source: 'swiss_dwellings', credit: 'All files: CC-BY-4.0. Credit: test.',
    files: [{ path: 'f.pdf', size: '1 kB', kind: 'Vector PDF', lane: 'CAD', role: 'source' },
      { path: 'f.png', size: '1 kB', kind: 'PNG rendering', lane: 'Vision', role: 'same', image: 'f.png' }],
    questions: [
      { question: 'How many doors (interior and entrance) are drawn on this floor plan?', answer: 12, unit: 'count', type: 'count' },
      { question: "How many rooms labelled 'Bad' are there on this floor?", answer: 2, unit: 'count', type: 'count' },
      { question: 'What is the net floor area of apartment A in m²?', answer: 50.5, unit: 'm2', type: 'area' },
      { question: 'What is the net floor area of apartment B in m²?', answer: 61.25, unit: 'm2', type: 'area' },
    ],
    archive_files: archiveFiles,
  };
  const ctx = vm.createContext({ window });
  for (const f of ['data.js', 'stoa.js', 'triage.js']) {
    // data.js exports to module.exports under node; here it must take the browser path (window.VData)
    const src = fs.readFileSync(path.join(__dirname, f), 'utf8').replace("typeof module !== 'undefined' && module.exports", 'false');
    vm.runInContext(src, ctx, { filename: f });
  }
  window.VData.__T = window.VTriage;
  return window.VData;
}

test('Stoa answers come from the answer key, by exact text or by every content word', () => {
  const V = load();
  const r = V.askProject('How many doors are there?');
  assert.equal(r.total, 12);
  assert.equal(r.total_unit, 'count');
  assert.equal(r.parts[0].answer.conflict, 'c1');  // the doors are a demo conflict; unsettled it shows the key's value
  assert.equal(r.parts[0].answer.marks.length, 0);
  assert.equal(V.askProject('net area of apartment B').total, 61.25);
  assert.equal(V.formatValue('area', 61.25), '61.25 m²');
  assert.equal(V.formatValue('door', 1), '1 door');
});

test('Stoa refuses a question the key does not hold, or one that matches several, offering the candidates', () => {
  const V = load();
  const many = V.askProject('What is the net floor area?');
  assert.equal(many.total, null);
  assert.equal(many.canAnswer.length, 2);
  const none = V.askProject('What is the area of the kitchen?');
  assert.equal(none.total, null);
  assert.ok(none.parts[0].answer.refusal);
  assert.equal(none.canAnswer.length, V.SUGGEST.length);
});

test('Stoa mode has one drawing, the demo conflicts its key supports, and rooms from the labelled counts', () => {
  const V = load();
  assert.equal(V.DRAWINGS.length, 1);
  assert.equal(V.CONFLICTS.length, 1);  // doors only: the fixture has no apartment A area or washbasin count
  assert.equal(V.askProject('How many doors are there?', { c1: 1 }).total, 11);  // the picked variant wins
  assert.equal(V.extractFacts().rooms.length, 2);
  assert.equal(V.extractFacts().doors, 12);
  assert.ok(V.CREDIT.includes('CC-BY-4.0'));
});

test('the archive folder: a plan is a drawing with no answer key, any other kind is set aside for triage', () => {
  const reg = (kind) => ({ kind, has_floor_plan: kind === 'floor_plan', photo_of_sheet: false, scale_shown: 'none', quality: 'good', method: 'hand-picked example' });
  const V = load([
    { path: 'archive/p.jpg', size: '1 kB', kind: 'JPG scan', image: 'archive/p.jpg', credit: 'c (PDM)', lane: 'Vision', role: 'source', plan: true },
    { path: 'archive/e.jpg', size: '1 kB', kind: 'JPG scan', image: 'archive/e.jpg', credit: 'c (PDM)', lane: null, role: 'not a floor plan',
      triage: { register: reg('elevation'), description: { text: 'A two-storey house.', what_it_is: 'drawing', shows_building: true, visible_text: 'EAST ELEVATION', detail: 'Two storeys under a roof.' } } },
  ]);
  const T = V.__T;
  assert.equal(V.DRAWINGS.map((d) => d.id).join(), 'stoa,a1');
  assert.equal(V.FILES.find((f) => f.path === 'archive/e.jpg').drawing, null);
  const r = V.askProject('How many doors are there?');
  assert.equal(r.total, 12);  // still the one drawing with an answer key
  assert.equal(r.parts.map((p) => !!p.answer.refusal).join(), 'false,true');  // join: arrays from the vm realm
  assert.equal(T.classOf('archive/e.jpg'), 'other_drawing');
  assert.ok(T.of('archive/e.jpg').example);
  assert.equal(T.relevanceOf('archive/e.jpg', T.projectOf(V)).verdict, 'unsure');  // "elevation" is a drawing word, no match
  const x = T.described('How many storeys does the building in the elevation have?', V.FILES);
  assert.equal(x.quote, 'A two-storey house. Two storeys under a roof.');
  assert.ok(T.picture('archive/e.jpg', 'e').startsWith('<img'));
});
