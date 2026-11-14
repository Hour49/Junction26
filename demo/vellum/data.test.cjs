// Run: node --test demo/vellum/
const test = require('node:test');
const assert = require('node:assert/strict');
const V = require('./data.js');

test('door count leaves open doorways out', () => {
  const a = V.answer('floor-02', 'How many doors are on this floor?', {});
  assert.equal(a.quantity, 'door');
  assert.equal(a.value, 14);
  assert.equal(a.marks.filter((m) => m.excluded).length, 2);
  assert.equal(a.check, null);
});

test('net area sums the flat rooms, not the stair', () => {
  const rooms = V.rooms(V.drawing('floor-02')).filter((r) => !r.common);
  const a = V.answer('floor-02', 'Net floor area?', {});
  const sum = Math.round(rooms.reduce((s, r) => s + r.area, 0) * 10) / 10;
  assert.equal(a.value, sum);
  assert.equal(a.marks.length, 14);
});

test('a conflict pick changes the answer, and the card labels agree with it', () => {
  const c1 = V.CONFLICTS[0];
  assert.deepEqual(V.variantLabels(c1), ['15 doors', '14 doors']);
  assert.equal(V.answer('floor-01', 'doors', { c1: 0 }).value, 15);
  assert.equal(V.answer('floor-01', 'doors', { c1: 1 }).value, 14);
  // c2: glazed opening as a door or a window moves one count to the other
  assert.equal(V.answer('floor-03', 'doors', { c2: 1 }).value, 15);
  assert.equal(V.answer('floor-03', 'windows', { c2: 0 }).value, 13);
  assert.equal(V.answer('floor-03', 'windows', { c2: 1 }).value, 12);
});

test('an open conflict makes the answer ask for a double-check', () => {
  const open = V.answer('flat-b12', 'How many windows?', {});
  assert.equal(open.value, 6);
  assert.notEqual(open.check, null);
  assert.ok(open.check.disputed.some((x) => x.mark_id === 'w7' && x.why.startsWith('Not settled')));
  const settled = V.answer('flat-b12', 'How many windows?', { c3: 1 });
  assert.equal(settled.value, 7);
  assert.ok(!settled.check.disputed.some((x) => x.mark_id === 'w7'));
});

test('rejecting marks lowers the value', () => {
  const a = V.answer('flat-c03', 'doors', {});
  assert.equal(V.valueOf(a.marks, 'door', { rejected: new Set(['d3']) }), a.value - 1);
});

test('check items follow the API shape: strongest first, at most 5, missed places add one', () => {
  const a = V.answer('flat-c03', 'How many windows?', {});
  const items = a.check.disputed;
  assert.ok(items.length <= 5);
  assert.equal(items[0].mark_id, null); // 2 readers against the answer: strongest
  assert.deepEqual(Object.keys(items[0].readers), ['answer', 'detector-m', 'seg']);
  assert.equal(V.valueOf(a.marks, 'window', { added: new Set([items[0].place]) }), a.value + 1);
});

test('unknown questions are refused with a reason', () => {
  const a = V.answer('floor-02', 'What fire rating do the stair doors need?', {});
  assert.equal(a.quantity, null);
  const r = V.answer('floor-02', 'Who designed this?', {});
  assert.equal(r.quantity, null);
  assert.ok(r.refusal.length > 0);
});

test('cross-checks disagree exactly where a conflict sits', () => {
  const bad = V.crossChecks().filter((p) => !p.agree);
  assert.equal(bad.length, V.CONFLICTS.length);
});

test('ingest progress ends with every file through and every drawing ready', () => {
  const start = V.progress(0);
  assert.equal(start.step, 0);
  assert.equal(start.ready, 0);
  const end = V.progress(999);
  assert.equal(end.done, true);
  assert.equal(end.through, V.FILES.length);
  assert.equal(end.ready, V.DRAWINGS.length);
  assert.equal(end.aside, 2);
});

test('the project chat totals one answer per drawing, or refuses with what can be asked', () => {
  const r = V.askProject('How many doors are there?', {});
  assert.equal(r.rows.length, V.DRAWINGS.length);
  assert.equal(r.total, r.rows.reduce((s, a) => s + a.value, 0));
  assert.equal(r.rows[0].drawing, V.DRAWINGS[0].id);
  const area = V.askProject('What is the net floor area?', {});
  assert.equal(area.quantity, 'area');
  assert.equal(area.total, Math.round(area.rows.reduce((s, a) => s + a.value, 0) * 10) / 10);
  const no = V.askProject('Who designed this?', {});
  assert.equal(no.rows, undefined);
  assert.ok(no.refusal && no.canAnswer.length > 0);
});
