// Run: node --test demo/vellum/  (the recorded examples of the full app in examples.js)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { EXAMPLES, find, viewOf } = require('./examples.js');
const parts = EXAMPLES.flatMap((ex) => ex.turns.flatMap((t) => t.parts.map((p) => ({ ex, t, p }))));
const inPage = ([x0, y0, x1, y1]) => x0 >= 0 && y0 >= 0 && x1 <= 1 && y1 <= 1 && x0 < x1 && y0 < y1;

test('every example has turns, a credit with its link and pictures that are in examples/ and small', () => {
  assert.deepEqual(EXAMPLES.map((x) => x.id), ['scan', 'flat', 'heat']);
  for (const ex of EXAMPLES) {
    assert.ok(ex.turns.length >= 1, ex.id);
    assert.match(ex.credit[0], /Public domain|MIT licence/, ex.id);  // never a NonCommercial drawing
    assert.match(ex.credit[1], /^https:\/\//);
    for (const img of Object.values(ex.images)) {
      const size = fs.statSync(path.join(__dirname, 'examples', img.src)).size;
      assert.ok(size > 0 && size < 300e3, `${img.src} ${size}`);
    }
  }
  assert.equal(find('nope'), null);
});

test('a count answer has one numbered mark per thing it counted, all on the page', () => {
  for (const { ex, p } of parts) {
    if (p.image) assert.ok(ex.images[p.image], `${ex.id} ${p.image}`);
    for (const b of p.marks || []) assert.ok(inPage(b), `${p.file} ${b}`);
    if (p.value !== undefined) assert.equal((p.marks || []).length, p.value, `${ex.id} ${p.file}`);
    // a radiator count read from a fact sheet: its marks are the radiators its total names
    const total = p.facts && p.image && p.facts.match(/^Total space heaters: (\d+)$/m);
    if (total) assert.equal(p.marks.length, Number(total[1]), p.file);
    assert.ok(['high', 'medium', 'low'].includes(p.level) && p.level_text.length > 20);
  }
});

test('the scan: 19 doors at Low, 3 places in dispute on marks it has or on a place it did not count; 1 toilet at High', () => {
  const [toilet, doors] = find('scan').turns;
  assert.equal(toilet.parts[0].value, 1);
  assert.equal(toilet.parts[0].level, 'high');
  const d = doors.parts[0];
  assert.equal(d.value, 19);
  assert.equal(d.level, 'low');
  assert.deepEqual(d.check.disputed.map((x) => x.mark), [19, null, 14]);
  for (const x of d.check.disputed) {
    assert.ok(inPage(x.box));
    if (x.mark !== null) assert.deepEqual(d.marks[x.mark - 1], x.box);  // the place is that mark
  }
  assert.equal(find('flat').turns[0].parts[0].value, 8);
  assert.equal(find('flat').turns[0].parts[0].level, 'high');
});

test('the figure shows every mark, or a window around the place in focus, inside the page', () => {
  for (const { p } of parts) {
    const boxes = (p.marks || []).concat(((p.check && p.check.disputed) || []).map((x) => x.box));
    const [x, y, w, h] = viewOf(boxes);
    assert.ok(x >= 0 && y >= 0 && x + w <= 1 + 1e-9 && y + h <= 1 + 1e-9);
    for (const b of boxes) assert.ok(b[0] >= x && b[1] >= y && b[2] <= x + w && b[3] <= y + h, `${p.file} ${b}`);
    for (const b of boxes.slice(0, 3)) {
      const [fx, fy, fw, fh] = viewOf(boxes, b);
      assert.ok(fx >= 0 && fy >= 0 && fx + fw <= 1 + 1e-9 && fy + fh <= 1 + 1e-9);
      assert.ok(b[0] >= fx && b[2] <= fx + fw && b[1] >= fy && b[3] <= fy + fh);  // the place itself is in its window
    }
  }
  assert.deepEqual(viewOf([]), [0, 0, 1, 1]);
});

function browser() {
  const window = { VPlan: { esc: (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`) } };
  window.window = window;
  const ctx = vm.createContext({ window });
  const src = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8').replace("typeof module !== 'undefined' && module.exports", 'false');
  vm.runInContext(src, ctx, { filename: 'examples.js' });
  return window.VExamples;
}

test('the start page lists every example, and an example page replays its turns as they are asked', () => {
  const X = browser();
  const cards = X.cards();
  for (const ex of EXAMPLES) assert.ok(cards.includes(`href="#/example/${ex.id}"`) && cards.includes(`../examples/${Object.values(ex.images)[0].src}`));
  let page = X.screen({ id: 'scan' });
  assert.ok(page.includes('How many toilets are there?') && page.includes('<b>1</b>') && page.includes('>High<'));
  assert.ok(page.includes('data-act="ex-ask"') && page.includes('And how many doors?'));  // not asked yet: a chip
  X.actions['ex-ask']({ dataset: { x: 'scan', i: '1' } });
  page = X.screen({ id: 'scan' });
  assert.ok(page.includes('<b>19</b>') && page.includes('>Low<') && !page.includes('data-act="ex-ask"'));
  assert.equal((page.match(/class="hl ok"/g) || []).length, 1 + 17);  // the toilet, and the doors not in dispute
  assert.equal((page.match(/class="hl"/g) || []).length, 2);  // marks 19 and 14
  assert.equal((page.match(/class="hl open"/g) || []).length, 1);  // the door one reader saw that was not counted
  X.actions['ex-focus']({ dataset: { x: 'scan', k: '1-0', i: '1' } });
  page = X.screen({ id: 'scan' });
  assert.ok(page.includes('aria-pressed="true"') && page.includes('Show every mark'));
  X.actions['ex-focus']({ dataset: { x: 'scan', k: '1-0', i: '1' } });
  assert.ok(!X.screen({ id: 'scan' }).includes('Show every mark'));
  const heat = X.screen({ id: 'heat' });
  assert.ok(heat.includes('H-101 E00 heating.png') && heat.includes('rwth-digitalhub_digitalhub-fm-hzg-v2.ifc') && heat.includes('Total space heaters: 63'));
});

test('the page template loads examples.js before app.js, and the build ships it with every picture', () => {
  const html = fs.readFileSync(path.join(__dirname, 'app.html'), 'utf8');
  assert.ok(html.indexOf('src="examples.js"') > 0 && html.indexOf('src="examples.js"') < html.indexOf('src="app.js"'));
  const build = fs.readFileSync(path.join(__dirname, '../../site/build-assets.sh'), 'utf8');
  assert.match(build, /\bexamples\.js\b/);
  for (const ex of EXAMPLES) for (const img of Object.values(ex.images)) assert.ok(build.includes(`examples/${img.src}`), img.src);
});
