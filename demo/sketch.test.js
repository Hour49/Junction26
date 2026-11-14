// node demo/sketch.test.js : stroke classifier and mark -> edit checks against the sample plan in app.js
const assert = require('assert'), fs = require('fs'), path = require('path');
const S = require('./sketch.js');
const src = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
const samplePlan = new Function(src.slice(src.indexOf('function samplePlan'), src.indexOf('const clone')) + 'return samplePlan;')();
const loop = (cx, cy, rx, ry) => Array.from({ length: 33 }, (_, i) => [cx + rx * Math.cos(i / 32 * 6.2), cy + ry * Math.sin(i / 32 * 6.2)]);
const line = (a, b) => Array.from({ length: 11 }, (_, i) => [a[0] + (b[0] - a[0]) * i / 10, a[1] + (b[1] - a[1]) * i / 10]);
const X = (c, r) => [line([c[0] - r, c[1] - r], [c[0] + r, c[1] + r]), line([c[0] + r, c[1] - r], [c[0] - r, c[1] + r])];
const run = (text, strokes, m = samplePlan()) => { const r = S.interpret(text, S.classify(strokes), m); if (r.apply) r.apply(m); return { r, m }; };

// classifier
assert.deepStrictEqual(S.classify([loop(5, 5, 1, 1)]).map((k) => k.kind), ['circle']);
const x = S.classify(X([3, 3], 0.4));
assert.deepStrictEqual(x.map((k) => k.kind), ['x']); assert(Math.hypot(x[0].at[0] - 3, x[0].at[1] - 3) < 1e-9);
assert.deepStrictEqual(S.classify([line([1, 1], [4, 1])]).map((k) => k.kind), ['arrow']);
assert.deepStrictEqual(S.classify([loop(2, 2, 1, 1), ...X([8, 2], 0.4), line([1, 6], [3, 6])]).map((k) => k.kind).sort(), ['arrow', 'circle', 'x']);
assert.deepStrictEqual(S.classify([[[1, 1], [1.05, 1.02]]]), []); // a dot is no mark

// circle in the hall next to the bathroom -> bathroom added, hall shrinks
let { r, m } = run('put a bathroom here', [loop(8.5, 6.2, 1, 1.75)]);
assert(r.text && /Bathroom 2/.test(r.text), r.text); assert(/part of the hall/.test(r.reading), r.reading);
const b2 = m.rooms.find((q) => q.id === 'bath2'), hall = m.rooms.find((q) => q.id === 'hall');
assert.deepStrictEqual([b2.x, b2.y, b2.w, b2.h], [7.5, 4.5, 2, 3.5]); assert.deepStrictEqual([hall.x, hall.w], [9.5, 2.5]);
// circle in the living room, away from the wet room -> ventilation refusal
assert.strictEqual(run('bathroom here', [loop(3, 2, 1, 1)]).r.rule, 'Ventilation of wet rooms');
// circle at the kitchen's north wall -> window added; circle in the middle of the plan -> refused
({ r, m } = run('put a window here', [loop(11, 0.4, 0.5, 0.5)]));
assert(/north wall of the kitchen/.test(r.text), r.text); assert.strictEqual(m.wins.length, 5);
assert.strictEqual(run('a window here', [loop(6, 4.5, 0.4, 0.4)]).r.rule, 'Windows in outside walls');
// X on walls / windows / door
assert.strictEqual(run("remove what I X'd", X([6, 4.5], 0.3)).r.rule, 'Load-bearing walls');
assert.strictEqual(run("remove what I X'd", X([12, 2], 0.3)).r.rule, 'Outside walls');
assert.strictEqual(run("remove what I X'd", X([12, 6], 0.3)).r.rule, 'Accessible entrance');
({ r, m } = run("remove what I X'd", X([7, 2], 0.3)));
assert(/kitchen and living room/.test(r.text), r.text); assert(m.rooms.some((q) => q.name === 'Living room + kitchen' && q.w === 12));
({ r, m } = run("remove what I X'd", X([1.4, 8], 0.3)));
assert(/bedroom window/.test(r.text)); assert.strictEqual(m.wins.length, 3);
assert.strictEqual(run("remove what I X'd", X([3.8, 8], 0.3), m).r.rule, 'Daylight in rooms for sleeping'); // last one
// arrow: window to the west wall; WC into the living room is refused
({ r, m } = run('move it here', [line([2.8, 0.2], [0.2, 2.5])]));
assert(/west wall of the living room/.test(r.text), r.text); assert.strictEqual(m.wins.find((w) => w.id === 'win1').x1, 0);
assert.strictEqual(run('move it here', [line([6.6, 7.3], [3, 2])]).r.rule, 'Drains for wet fixtures');
// marks without a request -> question with chips
assert.deepStrictEqual(run('hmm', [loop(8.5, 6.2, 1, 1.5)]).r.ask, ['Put a bathroom here', 'Put a window here']);
console.log('sketch tests ok');
