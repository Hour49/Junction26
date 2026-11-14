// The demo's reading steps and the pure functions that derive counts, totals and progress from a project's data. It
// holds no project: stoa.js fills VData with real files from the Stoa dataset (make_stoa_demo.py, local only), and
// nothing on screen is generated (Tudor: "just take data from the real dataset"). Plain script (global VData) and
// node-loadable.
(function (root) {
  'use strict';

  const LAYOUTS = {};  // real drawings are images: no drawn layouts

  const ARCHIVE = '';

  const FILES = [];

  const DRAWINGS = [];

  const CONFLICTS = [];  // the dataset has one reading per drawing, so no conflicts

  const QUANTITIES = {
    door: { noun: ['door', 'doors'], rule: 'Doors with a leaf are counted. Open doorways without a leaf are left out.' },
    window: { noun: ['window', 'windows'], rule: 'One window per opening in an outside wall, whatever the number of panes.' },
    room: { noun: ['room', 'rooms'], rule: 'Rooms of the flats. The stair and the balconies are left out.' },
    area: { noun: ['m²', 'm²'], rule: 'Net floor area: the rooms of the flats, inside the walls. The stair and the balconies are left out.' },
  };

  const STEPS = [
    ['Unpack', 'opening the zip safely', 'unpack', 1.6], ['Identify', 'what each file really is', 'identify', 1.8],
    ['Route', 'picking the best source per drawing', 'identify', 1.4], ['Normalise', 'upright sheets, views and scale', 'normalise', 1.6],
    ['Extract', 'rooms, doors, windows, fixtures', 'extract', 2.6], ['Drawing model', 'one schema for every drawing', 'extract', 1.4],
    ['Cross-check', 'a second, independent count', 'check', 2.0], ['Index', 'precomputing the answers', 'check', 1.2],
  ].map(([name, hint, panel, secs]) => ({ name, hint, panel, secs }));

  const drawing = (id) => {
    const d = DRAWINGS.find((x) => x.id === id);
    if (!d) throw new Error(`no drawing ${id}`);
    return d;
  };
  const layoutOf = (d) => LAYOUTS[d.layout];
  const conflictOf = (d, elementId) => CONFLICTS.find((c) => c.drawing === d.id && c.element === elementId) || null;

  // picks: { c1: 0 | 1 | null }. A conflict's reading: the person's pick, else the AI's, else variant 0 (shown as open).
  function readingOf(c, picks) {
    const p = picks && c.id in picks ? picks[c.id] : c.ai;
    return p === null || p === undefined ? { pick: c.ai === null ? 0 : c.ai, settled: false } : { pick: p, settled: true };
  }

  // The openings of a drawing as read, with conflicts applied.
  function openings(d, picks) {
    const base = layoutOf(d).openings.map(([id, kind, x, y]) => ({ id, kind, x, y, conflict: null }));
    const extra = d.extra.map(([id, kind, x, y, cid]) => {
      const c = CONFLICTS.find((k) => k.id === cid);
      const r = readingOf(c, picks);
      return { id, kind: c.variants[r.pick].kind, drawnAs: kind, x, y, conflict: { id: cid, settled: r.settled } };
    });
    return base.concat(extra);
  }

  function rooms(d) {
    const L = layoutOf(d);
    return L.rooms.map(([id, label, x, y, w, h, common]) => ({
      id, label, x, y, w, h, common: !!common, area: Math.round((w * h) / (L.scale * L.scale) * 10) / 10 }));
  }

  // The marks behind an answer: counted, left out by the rule (excluded), or not counted for an open conflict.
  function marksFor(d, quantity, picks) {
    if (quantity === 'room' || quantity === 'area') {
      return rooms(d).filter((r) => !r.common).map((r) => ({ id: r.id, room: r, counted: true, value: r.area }));
    }
    const out = [];
    for (const o of openings(d, picks)) {
      const shown = o.kind === quantity || (o.conflict && !o.conflict.settled && conflictOf(d, o.id).quantity === quantity);
      if (o.kind === quantity) out.push({ id: o.id, x: o.x, y: o.y, counted: true, value: 1, conflict: o.conflict });
      else if (quantity === 'door' && o.kind === 'doorway') out.push({ id: o.id, x: o.x, y: o.y, counted: false, excluded: true, value: 0 });
      else if (shown) out.push({ id: o.id, x: o.x, y: o.y, counted: false, value: 0, conflict: o.conflict });
    }
    for (const c of d.check) {
      if (c.mark_id === null && c.quantity === quantity) out.push({ id: c.id, x: c.x, y: c.y, counted: false, missed: true, value: 1 });
    }
    return out;
  }

  const round1 = (v) => Math.round(v * 10) / 10;

  // edits: { rejected: Set of mark ids, added: Set of missed place ids } from a person fixing the answer.
  function valueOf(marks, quantity, edits) {
    const rej = (edits && edits.rejected) || new Set(), add = (edits && edits.added) || new Set();
    const kept = marks.filter((m) => (m.counted && !rej.has(m.id)) || (m.missed && add.has(m.id)));
    return quantity === 'area' ? round1(kept.reduce((s, m) => s + m.value, 0)) : kept.length;
  }

  // The answer's check items (answer.check.disputed): the drawing's items that touch these marks, plus any mark tied to an
  // unsettled conflict; strongest first (most readers disagreeing with the answer), at most 5.
  function disputed(d, marks) {
    const ids = new Set(marks.map((m) => m.id));
    const out = [];
    for (const m of marks) {
      if (!m.conflict || m.conflict.settled) continue;
      const c = conflictOf(d, m.id);
      out.push({ mark_id: m.id, why: `Not settled yet: “${c.title}” Settle it in Conflicts.`,
        readers: { answer: m.counted ? `a ${c.quantity}` : 'nothing', ...c.readers } });
    }
    for (const c of d.check) {
      if (ids.has(c.mark_id === null ? c.id : c.mark_id)) out.push({ mark_id: c.mark_id, place: c.mark_id === null ? c.id : null, why: c.why, readers: c.readers });
    }
    const against = (x) => Object.entries(x.readers).filter(([k, v]) => k !== 'answer' && v !== x.readers.answer).length;
    return out.map((x, i) => ({ x, i })).sort((a, b) => against(b.x) - against(a.x) || a.i - b.i).map((e) => e.x).slice(0, 5);
  }

  // Numbers 1..n on the counted marks, in mark order; uncounted marks get none.
  function numbered(marks) {
    let n = 0;
    return marks.map((m) => ({ ...m, n: m.counted ? ++n : null }));
  }

  function parseQuestion(text) {
    const t = text.toLowerCase();
    // shortcut: keyword match, a question about a property of doors (fire rating, cost) is refused rather than counted
    if (/\b(fire|rating|cost|price|who|when|why|material|height|width)\b/.test(t)) return null;
    if (/\b(area|m2|m²|square|floor space)\b/.test(t)) return 'area';
    if (/\bdoors?\b/.test(t)) return 'door';
    if (/\bwindows?\b/.test(t)) return 'window';
    if (/\brooms?\b/.test(t)) return 'room';
    return null;
  }

  const ROOM_LABELS = [...new Set(DRAWINGS.flatMap((d) => rooms(d).filter((r) => !r.common).map((r) => r.label)))];

  function answer(drawingId, question, picks) {
    const d = drawing(drawingId);
    const quantity = parseQuestion(question);
    if (!quantity) {
      return { drawing: d.id, question, quantity: null,
        refusal: 'I can count doors, windows and rooms and measure the net floor area on a drawing. This question asks for something the drawing model does not hold, so there is no number to point at.' };
    }
    let all = marksFor(d, quantity, picks);
    // an area question that names rooms ("the kitchen") sums those rooms only; a drawing without them does not answer
    const named = quantity === 'area' ? ROOM_LABELS.filter((l) => new RegExp(`\\b${l}\\b`, 'i').test(question)) : [];
    if (named.length) {
      all = all.filter((m) => named.includes(m.room.label));
      if (!all.length) return { drawing: d.id, question, quantity: null, refusal: `This drawing has no ${named.join(' or ').toLowerCase()}.` };
    }
    const marks = numbered(all);
    const dis = disputed(d, marks);
    const certified = d.lane === 'CAD' && dis.length === 0;
    const reason = dis.some((x) => x.why.startsWith('Not settled'))
      ? 'A conflict on this drawing is not settled yet.'
      : 'Read from a scan by vision, and the readers do not all agree.';
    return { drawing: d.id, question, quantity, refusal: null, marks, rooms: named,
      value: valueOf(marks, quantity, null), check: certified ? null : { reason, disputed: dis } };
  }

  // The counting rule shown under an answer; an area of named rooms says which rooms.
  function ruleOf(a) {
    return a.rooms && a.rooms.length ? `Net floor area of the ${a.rooms.join(' and ').toLowerCase()}, inside the walls.` : QUANTITIES[a.quantity].rule;
  }

  function noun(quantity, value) {
    const [one, many] = QUANTITIES[quantity].noun;
    return value === 1 ? one : many;
  }

  function formatValue(quantity, value) {
    return quantity === 'area' ? `${value.toFixed(1)} m²` : `${value} ${noun(quantity, value)}`;
  }

  // The two readings of a conflict, as counts of its quantity on its drawing.
  function variantLabels(c) {
    const d = drawing(c.drawing);
    return c.variants.map((v, i) => v.label || formatValue(c.quantity, valueOf(marksFor(d, c.quantity, { [c.id]: i }), c.quantity)));
  }

  // Cross-check pairs: per drawing and count, the first and the second reading. They differ only where a conflict sits.
  function crossChecks() {
    const pairs = [];
    for (const d of DRAWINGS) {
      for (const q of ['door', 'window']) {
        const c = CONFLICTS.find((k) => k.drawing === d.id && k.quantity === q);
        const count = (picks) => valueOf(marksFor(d, q, picks), q);
        const a = c ? count({ [c.id]: 0 }) : count({});
        const b = c ? count({ [c.id]: 1 }) : a;
        pairs.push({ drawing: d.name, quantity: q, a, b, agree: a === b });
      }
    }
    return pairs;
  }

  // Ingest progress at t seconds: the running step, overall fraction, and the derived stats.
  function progress(t, files = FILES, drawingCount = DRAWINGS.length) {
    const total = STEPS.reduce((s, x) => s + x.secs, 0);
    let acc = 0, step = STEPS.length, within = 1;
    for (let i = 0; i < STEPS.length; i++) {
      if (t < acc + STEPS[i].secs) { step = i; within = (t - acc) / STEPS[i].secs; break; }
      acc += STEPS[i].secs;
    }
    const done = step >= STEPS.length;
    const frac = done ? 1 : Math.max(0, t) / total;
    const drawings = drawingCount, aside = files.filter((f) => !f.drawing).length;
    files = files.length;
    // files move through during Unpack..Route; drawings become ready during Extract..Index
    const through = done ? files : Math.min(files, Math.floor(files * Math.min(1, (step + within) / 3)));
    const ready = done ? drawings : Math.max(0, Math.min(drawings, Math.floor(drawings * ((step + within) - 4) / 4)));
    return { step, within, done, frac, total, files, through, drawings, ready, aside: step >= 1 || done ? aside : 0 };
  }

  // The project chat, in the shape of POST /api/projects/{id}/ask (#135): one question asked of every drawing; parts
  // that answered first, then those that refused. A total only when exactly one drawing answers (Bogdan, #14
  // c6875696652): drawings may show the same rooms, so parts are not added up. The other case of the rule (storeys of
  // one IFC model) does not occur in this sample. total_note is always one sentence.
  const CAN_ANSWER = ['How many doors are there?', 'How many windows are there?', 'What is the net floor area?', 'How many rooms are there?'];
  const TOTAL_NOTE = 'These drawings may show the same rooms, so the numbers are not added up.';
  function askProject(question, picks) {
    const answers = DRAWINGS.map((d) => answer(d.id, question, picks));
    const ok = answers.filter((a) => !a.refusal);
    const parts = ok.concat(answers.filter((a) => a.refusal)).map((a) => ({ drawing_id: a.drawing, name: drawing(a.drawing).name, answer: a }));
    const one = ok.length === 1 ? ok[0] : null;
    return { question, parts, total: one ? one.value : null, total_unit: one ? (one.quantity === 'area' ? 'm2' : 'count') : null,
      total_sure: !!one && !one.check,
      total_note: one ? `From ${drawing(one.drawing).name}, the one drawing that answered.` : ok.length ? TOTAL_NOTE : 'No drawing can answer this.',
      canAnswer: ok.length ? null : CAN_ANSWER };
  }

  // What the Extract panel shows: the drawing, its rooms and the counts read from it.
  function extractFacts() {
    const d = drawing('ground-floor');
    return { drawing: d, rooms: rooms(d), doors: valueOf(marksFor(d, 'door', {}), 'door'), windows: valueOf(marksFor(d, 'window', {}), 'window') };
  }

  // "Read it as a floor plan" (decision 0010, POST …/triage): the annex sketch has a layout, so reading it gives drawing
  // 7; the other set-aside images have none, so their reading finds nothing and they get no drawing.
  const READ_AS_PLAN = {};  // a real set-aside file has no reading to give
  const BASE_DRAWINGS = DRAWINGS.length;
  // Returns the new drawing, or null when the file has no layout to read. Idempotent.
  function readAsPlan(path) {
    const d = READ_AS_PLAN[path], f = FILES.find((x) => x.path === path);
    if (!d || !f) return null;
    if (!DRAWINGS.includes(d)) { DRAWINGS.push(d); Object.assign(f, { drawing: d.id, lane: d.lane, role: 'read' }); }
    return d;
  }
  // A new workspace starts from the sample as uploaded.
  function resetReadAsPlan() {
    DRAWINGS.length = BASE_DRAWINGS;
    for (const path of Object.keys(READ_AS_PLAN)) Object.assign(FILES.find((x) => x.path === path), { drawing: null, lane: null, role: 'not a floor plan' });
  }

  const API = { readAsPlan, resetReadAsPlan, READ_AS_PLAN, extractFacts, askProject, LAYOUTS, ARCHIVE, FILES, DRAWINGS, CONFLICTS, QUANTITIES, STEPS, drawing, layoutOf, rooms, openings,
    marksFor, valueOf, disputed, parseQuestion, answer, ruleOf, noun, formatValue, variantLabels, crossChecks, progress, readingOf };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.VData = API;
})(typeof window !== 'undefined' ? window : globalThis);
