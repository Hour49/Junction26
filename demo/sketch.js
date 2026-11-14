/* Pen marks on the plan ("Edit my plan"): classify strokes, find what they point at, turn marks + chat text into an
   edit. Pure functions over the plan model from app.js (metres). No ML: a closed loop is a circle (its box is the
   target area), two crossing lines are an X (the crossing is the target point), an open line is an arrow.
   Mock only: the rules are examples, not legal advice. */
const Sketch = (() => {
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const len = (pts) => pts.reduce((s, p, i) => s + (i ? dist(pts[i - 1], p) : 0), 0);
  const bbox = (pts) => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
  };
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  // crossing point of segments ab and cd, or null
  function meet(a, b, c, d) {
    const d1 = cross(a, b, c), d2 = cross(a, b, d), d3 = cross(c, d, a), d4 = cross(c, d, b);
    if (d1 * d2 >= 0 || d3 * d4 >= 0) return null;
    const t = d1 / (d1 - d2);
    return [c[0] + t * (d[0] - c[0]), c[1] + t * (d[1] - c[1])];
  }

  // strokes: arrays of [x, y] in metres -> marks: {kind: 'circle', box} | {kind: 'x', at} | {kind: 'arrow', from, to}
  function classify(strokes) {
    const S = strokes.filter((s) => s.length > 1).map((p) => ({ p, L: len(p), gap: dist(p[0], p[p.length - 1]), b: bbox(p) }));
    const marks = [], used = new Set();
    S.forEach((s, i) => {
      if (s.L > 1 && s.gap < Math.max(0.6, 0.3 * s.L) && s.b.w > 0.4 && s.b.h > 0.4) { marks.push({ kind: 'circle', box: s.b }); used.add(i); }
    });
    const lines = S.map((s, i) => i).filter((i) => !used.has(i) && S[i].L >= 0.4);
    for (const i of lines) for (const j of lines) {
      if (j <= i || used.has(i) || used.has(j)) continue;
      const a = S[i].p, b = S[j].p, at = meet(a[0], a[a.length - 1], b[0], b[b.length - 1]);
      if (at) { marks.push({ kind: 'x', at }); used.add(i); used.add(j); }
    }
    for (const i of lines) if (!used.has(i)) { const p = S[i].p; marks.push({ kind: 'arrow', from: p[0], to: p[p.length - 1] }); }
    return marks;
  }

  // ---- hit-testing on the plan model
  function segDist(p, o) {
    const dx = o.x2 - o.x1, dy = o.y2 - o.y1, l2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((p[0] - o.x1) * dx + (p[1] - o.y1) * dy) / l2));
    return { d: Math.hypot(p[0] - o.x1 - t * dx, p[1] - o.y1 - t * dy), at: [o.x1 + t * dx, o.y1 + t * dy] };
  }
  const roomAt = (m, p) => m.rooms.filter((r) => p[0] >= r.x && p[0] <= r.x + r.w && p[1] >= r.y && p[1] <= r.y + r.h)
    .sort((a, b) => a.w * a.h - b.w * b.h)[0];
  // nearest element to p: openings and fixtures first (they sit on or near walls), then walls
  function nearest(m, p, max) {
    const pick = (list, f) => list.map((o) => ({ o, d: f(o) })).filter((x) => x.d <= max).sort((a, b) => a.d - b.d)[0];
    const h = pick(m.wins, (o) => segDist(p, o).d) || pick(m.doors, (o) => segDist(p, o).d)
      || pick(m.fx, (o) => dist(p, [o.x, o.y])) || pick(m.walls, (o) => segDist(p, o).d);
    if (!h) return null;
    const kind = m.wins.includes(h.o) ? 'win' : m.doors.includes(h.o) ? 'door' : m.fx.includes(h.o) ? 'fx' : 'wall';
    return { kind, o: h.o };
  }
  const roomsBeside = (m, w) => m.rooms.filter((r) => (w.x1 === w.x2
    ? (Math.abs(r.x - w.x1) < 1e-6 || Math.abs(r.x + r.w - w.x1) < 1e-6) && r.y < Math.max(w.y1, w.y2) && r.y + r.h > Math.min(w.y1, w.y2)
    : (Math.abs(r.y - w.y1) < 1e-6 || Math.abs(r.y + r.h - w.y1) < 1e-6) && r.x < Math.max(w.x1, w.x2) && r.x + r.w > Math.min(w.x1, w.x2)));
  const lc = (s) => s.toLowerCase();
  const FX = { wc: 'WC', shower: 'shower', sink: 'sink' };
  function describe(m, h) {
    if (!h) return 'an empty spot';
    const o = h.o;
    if (h.kind === 'win') return `the ${lc((m.rooms.find((r) => r.id === o.room) || { name: '' }).name)} window`.replace('the  ', 'a ');
    if (h.kind === 'door') return `the ${o.name}`;
    if (h.kind === 'fx') { const r = roomAt(m, [o.x, o.y]); return `the ${FX[o.t]}${r ? ` in the ${lc(r.name)}` : ''}`; }
    if (o.name) return `the ${o.name}`;
    const rs = roomsBeside(m, o);
    if (o.ext) return `the outside wall of the ${lc((rs[0] || { name: 'flat' }).name)}`;
    return rs.length >= 2 ? `the wall between the ${lc(rs[0].name)} and the ${lc(rs[1].name)}` : 'a wall';
  }
  function circled(m, box) {
    const c = [box.x + box.w / 2, box.y + box.h / 2], r = roomAt(m, c);
    if (!r) return { room: null, text: `an area outside the plan, ${box.w.toFixed(1)} × ${box.h.toFixed(1)} m` };
    const whole = (box.w * box.h) / (r.w * r.h) > 0.8;
    return { room: r, text: `${whole ? 'the' : 'part of the'} ${lc(r.name)}, ${box.w.toFixed(1)} × ${box.h.toFixed(1)} m` };
  }
  // what the user's marks say, in words, so they see it was understood
  function read(m, marks) {
    return marks.map((k) => (k.kind === 'circle' ? `You circled ${circled(m, k.box).text}.`
      : k.kind === 'x' ? `You crossed out ${describe(m, nearest(m, k.at, 0.6))}.`
        : `You drew an arrow from ${describe(m, nearest(m, k.from, 0.8))} to ${describe(m, nearest(m, k.to, 0.8) || null).replace('an empty spot', (roomAt(m, k.to) ? `the ${lc(roomAt(m, k.to).name)}` : 'outside the plan'))}.`)).join(' ');
  }

  // ---- rules (examples, not legal advice)
  const RULES = {
    lb: { rule: 'Load-bearing walls', why: 'The middle wall carries the floor above. Removing it needs a structural engineer\'s design and a building permit, so I won\'t draw it as a simple edit.' },
    ext: { rule: 'Outside walls', why: 'An outside wall carries the roof and keeps the weather out. Removing it is not a plan edit.' },
    winExt: { rule: 'Windows in outside walls', why: 'A window gives daylight from outside, so it has to go in an outside wall. The spot you marked is an inside wall.' },
    bedWin: { rule: 'Daylight in rooms for sleeping', why: 'A bedroom needs a window to the outside for daylight and a way out in an emergency. This is its only window.' },
    door: { rule: 'Accessible entrance', why: 'The entrance door is the exit route. The flat can\'t be without it.' },
    vent: { rule: 'Ventilation of wet rooms', why: 'A bathroom needs mechanical exhaust ventilation and a drain. The spot you circled doesn\'t touch the existing bathroom, so there is no route to the ventilation shaft (assumed).' },
    drain: { rule: 'Drains for wet fixtures', why: 'A WC, shower or sink needs a drain. Outside a wet room there is none (assumed), so it can\'t go there.' },
    size: { rule: 'Minimum size of a bathroom', why: 'The area you circled is too small for a bathroom with a WC and a shower (at least 1.5 m each way in this example).' },
  };
  const refuse = (k, target) => ({ refuse: target, ...RULES[k] });
  const snap = (v) => Math.round(v * 10) / 10;

  function addBath(m, box) {
    const host = roomAt(m, [box.x + box.w / 2, box.y + box.h / 2]);
    if (!host) return { ask: ['Put a bathroom here'], note: 'That spot is outside the plan. Circle a place inside a room.' };
    if (host.wet) return { ask: ['Put a window here'], note: `The ${lc(host.name)} is already a wet room.` };
    // clip to the host room and snap edges within 0.4 m to its walls
    let x0 = Math.max(box.x, host.x), y0 = Math.max(box.y, host.y), x1 = Math.min(box.x + box.w, host.x + host.w), y1 = Math.min(box.y + box.h, host.y + host.h);
    const sn = (v, a, b) => (Math.abs(v - a) < 0.4 ? a : Math.abs(v - b) < 0.4 ? b : snap(v));
    x0 = sn(x0, host.x, host.x + host.w); x1 = sn(x1, host.x, host.x + host.w); y0 = sn(y0, host.y, host.y + host.h); y1 = sn(y1, host.y, host.y + host.h);
    const w = +(x1 - x0).toFixed(2), h = +(y1 - y0).toFixed(2);
    if (w < 1.5 || h < 1.5) return refuse('size', host.id);
    const touches = (r) => r.wet && ((Math.abs(r.x + r.w - x0) < 1e-6 || Math.abs(r.x - x1) < 1e-6) && Math.min(r.y + r.h, y1) - Math.max(r.y, y0) >= 0.5
      || (Math.abs(r.y + r.h - y0) < 1e-6 || Math.abs(r.y - y1) < 1e-6) && Math.min(r.x + r.w, x1) - Math.max(r.x, x0) >= 0.5);
    if (!m.rooms.some(touches)) return refuse('vent', host.id);
    const n = m.rooms.filter((r) => /^Bathroom/.test(r.name)).length + 1, id = `bath${n}`;
    return {
      text: `Added Bathroom ${n} where you circled, ${w.toFixed(1)} × ${h.toFixed(1)} m, next to the existing bathroom so it can share the ventilation shaft and drain (assumed). WC, shower and sink included.`,
      apply: (mm) => {
        const hr = mm.rooms.find((r) => r.id === host.id), full = (a, b, c, d) => Math.abs(a - c) < 1e-6 && Math.abs(b - d) < 1e-6;
        if (full(y0, y1, hr.y, hr.y + hr.h) && Math.abs(x0 - hr.x) < 1e-6) { hr.x = x1; hr.w = +(hr.w - w).toFixed(2); }
        else if (full(y0, y1, hr.y, hr.y + hr.h) && Math.abs(x1 - hr.x - hr.w) < 1e-6) hr.w = +(hr.w - w).toFixed(2);
        else if (full(x0, x1, hr.x, hr.x + hr.w) && Math.abs(y0 - hr.y) < 1e-6) { hr.y = y1; hr.h = +(hr.h - h).toFixed(2); }
        else if (full(x0, x1, hr.x, hr.x + hr.w) && Math.abs(y1 - hr.y - hr.h) < 1e-6) hr.h = +(hr.h - h).toFixed(2);
        mm.rooms.push({ id, name: `Bathroom ${n}`, x: x0, y: y0, w, h, wet: true });
        const on = (wl) => mm.walls.some((q) => q.x1 === q.x2 && wl.x1 === wl.x2 && Math.abs(q.x1 - wl.x1) < 1e-6 && Math.min(q.y1, q.y2) <= wl.y1 + 1e-6 && Math.max(q.y1, q.y2) >= wl.y2 - 1e-6
          || q.y1 === q.y2 && wl.y1 === wl.y2 && Math.abs(q.y1 - wl.y1) < 1e-6 && Math.min(q.x1, q.x2) <= wl.x1 + 1e-6 && Math.max(q.x1, q.x2) >= wl.x2 - 1e-6);
        [[x0, y0, x1, y0], [x0, y1, x1, y1], [x0, y0, x0, y1], [x1, y0, x1, y1]].forEach(([a, b, c, d], k) => {
          const wl = { id: `${id}w${k}`, x1: a, y1: b, x2: c, y2: d };
          if (!on(wl)) mm.walls.push(wl);
        });
        mm.fx.push({ id: `${id}s`, t: 'shower', x: x0 + 0.45, y: y0 + 0.45 }, { id: `${id}k`, t: 'sink', x: x1 - 0.4, y: y0 + 0.35 }, { id: `${id}c`, t: 'wc', x: x1 - 0.4, y: y1 - 0.5 });
      },
    };
  }

  // nearest outside wall to p within max metres, with the foot point
  function outsideWall(m, p, max) {
    return m.walls.filter((w) => w.ext).map((w) => ({ w, ...segDist(p, w) })).filter((x) => x.d <= max).sort((a, b) => a.d - b.d)[0];
  }
  function placeWin(w, at, size) {
    const hor = w.y1 === w.y2, lo = Math.min(hor ? w.x1 : w.y1, hor ? w.x2 : w.y2), hi = Math.max(hor ? w.x1 : w.y1, hor ? w.x2 : w.y2);
    const c = Math.max(lo + size / 2, Math.min(hi - size / 2, snap(hor ? at[0] : at[1])));
    return hor ? { x1: snap(c - size / 2), y1: w.y1, x2: snap(c + size / 2), y2: w.y1 } : { x1: w.x1, y1: snap(c - size / 2), x2: w.x1, y2: snap(c + size / 2) };
  }
  const SIDE = (w) => (w.y1 === w.y2 ? (w.y1 === 0 ? 'north' : 'south') : (w.x1 === 0 ? 'west' : 'east'));
  const inside = (m, seg) => roomAt(m, [(seg.x1 + seg.x2) / 2 + (seg.x1 === seg.x2 ? (seg.x1 === 0 ? 0.2 : -0.2) : 0), (seg.y1 + seg.y2) / 2 + (seg.y1 === seg.y2 ? (seg.y1 === 0 ? 0.2 : -0.2) : 0)]);

  function addWin(m, box) {
    const c = [box.x + box.w / 2, box.y + box.h / 2], hit = outsideWall(m, c, Math.max(box.w, box.h) / 2 + 0.6);
    if (!hit) { const n = nearest(m, c, 1); return refuse('winExt', n && n.kind === 'wall' ? n.o.id : (roomAt(m, c) || {}).id); }
    const seg = placeWin(hit.w, hit.at, 1.4), r = inside(m, seg), id = `win${m.wins.length + 1}x`;
    return {
      text: `Added a 1.4 m window on the ${SIDE(hit.w)} wall${r ? ` of the ${lc(r.name)}` : ''}, where you circled.`,
      apply: (mm) => mm.wins.push({ id, room: r ? r.id : null, ...seg }),
    };
  }

  function removeAt(m, at) {
    const h = nearest(m, at, 0.6);
    if (!h) return { ask: ['Remove what I X\'d'], note: 'I couldn\'t find a wall, window, door or fixture under your X. Draw it right on top of the element.' };
    const o = h.o, what = describe(m, h);
    if (h.kind === 'wall' && o.lb) return refuse('lb', o.id);
    if (h.kind === 'wall' && o.ext) return refuse('ext', o.id);
    if (h.kind === 'door') return refuse('door', o.id);
    if (h.kind === 'win') {
      const r = m.rooms.find((x) => x.id === o.room);
      if (r && /bed/i.test(r.name) && m.wins.filter((x) => x.room === o.room).length <= 1) return refuse('bedWin', o.id);
      return { text: `Removed ${what}.`, apply: (mm) => { mm.wins = mm.wins.filter((x) => x.id !== o.id); } };
    }
    if (h.kind === 'fx') return { text: `Removed ${what}.`, apply: (mm) => { mm.fx = mm.fx.filter((x) => x.id !== o.id); } };
    return {
      text: `Removed ${what}.`,
      apply: (mm) => {
        mm.walls = mm.walls.filter((x) => x.id !== o.id);
        const [a, b] = roomsBeside(mm, o), same = (p, q) => Math.abs(p - q) < 1e-6;
        if (a && b && (o.x1 === o.x2 ? same(a.y, b.y) && same(a.h, b.h) : same(a.x, b.x) && same(a.w, b.w))) {
          const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
          const u = { id: `${a.id}+${b.id}`, name: `${a.name} + ${lc(b.name)}`, x, y, w: +(Math.max(a.x + a.w, b.x + b.w) - x).toFixed(2), h: +(Math.max(a.y + a.h, b.y + b.h) - y).toFixed(2) };
          if (a.wet || b.wet) u.wet = true;
          mm.rooms = mm.rooms.filter((r) => r !== a && r !== b); mm.rooms.unshift(u);
        }
      },
    };
  }

  function moveBy(m, from, to) {
    const h = nearest(m, from, 0.8);
    if (!h || (h.kind !== 'win' && h.kind !== 'fx')) return { ask: ['Move it here'], note: 'Start the arrow on a window or a fixture (WC, shower, sink).' };
    const o = h.o, what = describe(m, h);
    if (h.kind === 'win') {
      const hit = outsideWall(m, to, 1);
      if (!hit) { const n = nearest(m, to, 1); return refuse('winExt', n && n.kind === 'wall' ? n.o.id : (roomAt(m, to) || {}).id); }
      const seg = placeWin(hit.w, hit.at, Math.hypot(o.x2 - o.x1, o.y2 - o.y1)), r = inside(m, seg);
      return { text: `Moved ${what} to the ${SIDE(hit.w)} wall${r ? ` of the ${lc(r.name)}` : ''}.`, apply: (mm) => Object.assign(mm.wins.find((x) => x.id === o.id), seg, { room: r ? r.id : o.room }) };
    }
    const r = roomAt(m, to);
    if (!r || !r.wet) return refuse('drain', r ? r.id : null);
    return { text: `Moved ${what} to the spot you marked in the ${lc(r.name)}.`, apply: (mm) => Object.assign(mm.fx.find((x) => x.id === o.id), { x: snap(to[0]), y: snap(to[1]) }) };
  }

  // marks + chat text -> { reading, ask?, note? } | { reading, refuse, rule, why } | { reading, text, apply(model) }
  // The text decides what, the marks decide where. Uses the first mark that fits the request.
  function interpret(text, marks, m) {
    const t = lc(text), reading = read(m, marks), first = (k) => marks.find((x) => x.kind === k);
    const chips = [...new Set(marks.map((k) => ({ circle: ['Put a bathroom here', 'Put a window here'], x: ['Remove what I X\'d'], arrow: ['Move it here'] }[k.kind])).flat())];
    let r = null;
    if (/bath|wc|toilet|kylpy|vessa/.test(t) && first('circle')) r = addBath(m, first('circle').box);
    else if (/window|ikkuna/.test(t) && first('arrow') && /move|here|there|siirr/.test(t)) r = moveBy(m, first('arrow').from, first('arrow').to);
    else if (/window|ikkuna/.test(t) && first('circle')) r = addWin(m, first('circle').box);
    else if (/remove|delete|x'?d|cross|take out|get rid|knock|poista/.test(t) && first('x')) r = removeAt(m, first('x').at);
    else if (/move|here|there|siirr/.test(t) && first('arrow')) r = moveBy(m, first('arrow').from, first('arrow').to);
    if (!r) r = { ask: chips, note: 'What should go here?' };
    return { reading, ...r };
  }

  // the user's ink as SVG (strokes in metres, e px per metre)
  const inkSVG = (strokes, e) => `<g class="ep-ink">${strokes.map((s) => `<polyline points="${s.map(([x, y]) => `${(x * e).toFixed(1)},${(y * e).toFixed(1)}`).join(' ')}"/>`).join('')}</g>`;

  return { classify, nearest, read, interpret, inkSVG };
})();
if (typeof module !== 'undefined') module.exports = Sketch;
