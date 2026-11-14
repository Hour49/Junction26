// Synthetic data for the Vellum clickable demo, and the pure functions that derive every count, mark and total
// shown on screen. Nothing here comes from a real archive. Loaded as a plain script (global VData) and by node --test.
(function (root) {
  'use strict';

  // Layouts: rooms as rectangles [x, y, w, h] in drawing units, `scale` units per metre.
  // Openings: kind 'door' | 'window' | 'doorway' (an open doorway, left out by the door rule).
  const LAYOUTS = {
    twoFlats: {
      view: [-15, -15, 630, 366], scale: 30,
      rooms: [
        ['a-living', 'Living', 0, 0, 150, 165], ['a-kitchen', 'Kitchen', 150, 0, 105, 96],
        ['a-hall', 'Hall', 150, 96, 105, 69], ['a-bed', 'Bedroom', 0, 165, 126, 135],
        ['a-bath', 'Bath', 126, 165, 69, 78], ['a-wc', 'WC', 195, 165, 60, 78], ['a-store', 'Store', 126, 243, 129, 57],
        ['stair', 'Stair', 255, 0, 90, 300, 'common'],
        ['b-living', 'Living', 450, 0, 150, 165], ['b-kitchen', 'Kitchen', 345, 0, 105, 96],
        ['b-hall', 'Hall', 345, 96, 105, 69], ['b-bed', 'Bedroom', 474, 165, 126, 135],
        ['b-bath', 'Bath', 405, 165, 69, 78], ['b-wc', 'WC', 345, 165, 60, 78], ['b-store', 'Store', 345, 243, 129, 57],
      ],
      outdoor: [[0, 300, 126, 36], [474, 300, 126, 36]],
      openings: [
        ['d1', 'door', 255, 132], ['d2', 'door', 150, 132], ['d3', 'door', 60, 165], ['d4', 'door', 177, 165],
        ['d5', 'door', 225, 165], ['d6', 'door', 126, 273], ['d7', 'door', 60, 300], ['d8', 'door', 345, 132],
        ['d9', 'door', 450, 132], ['d10', 'door', 540, 165], ['d11', 'door', 423, 165], ['d12', 'door', 375, 165],
        ['d13', 'door', 474, 273], ['d14', 'door', 540, 300], ['o1', 'doorway', 198, 96], ['o2', 'doorway', 402, 96],
        ['w1', 'window', 40, 0], ['w2', 'window', 110, 0], ['w3', 'window', 202, 0], ['w4', 'window', 398, 0],
        ['w5', 'window', 490, 0], ['w6', 'window', 560, 0], ['w7', 'window', 0, 82], ['w8', 'window', 0, 232],
        ['w9', 'window', 600, 82], ['w10', 'window', 600, 232], ['w11', 'window', 190, 300], ['w12', 'window', 410, 300],
      ],
    },
    flatB: {
      view: [-28, -28, 338, 296], scale: 24,
      rooms: [
        ['living', 'Living', 42, 0, 144, 138], ['kitchen', 'Kitchen', 186, 0, 96, 90], ['hall', 'Hall', 186, 90, 96, 48],
        ['bed1', 'Bedroom', 42, 138, 102, 102], ['bed2', 'Bedroom', 144, 138, 78, 102], ['bath', 'Bath', 222, 138, 60, 60],
        ['sauna', 'Sauna', 222, 198, 60, 42],
      ],
      outdoor: [[0, 18, 42, 90]],
      openings: [
        ['d1', 'door', 282, 114], ['d2', 'door', 186, 114], ['d3', 'door', 93, 138], ['d4', 'door', 183, 138],
        ['d5', 'door', 252, 138], ['d6', 'door', 252, 198], ['d7', 'door', 42, 120],
        ['w1', 'window', 114, 0], ['w2', 'window', 234, 0], ['w3', 'window', 42, 20], ['w4', 'window', 42, 189],
        ['w5', 'window', 93, 240], ['w6', 'window', 183, 240],
      ],
    },
    groundFloor: {
      view: [140, 130, 490, 280], scale: 26,
      rooms: [
        ['bath', 'Bath', 160, 150, 84, 110], ['hall', 'Hall', 244, 150, 132, 110], ['kitchen', 'Kitchen', 376, 150, 100, 110],
        ['pantry', 'Pantry', 476, 150, 134, 110], ['room1', 'Room', 160, 260, 86, 130], ['living', 'Living', 246, 260, 154, 130],
        ['dining', 'Dining', 400, 260, 126, 130], ['room2', 'Room', 526, 260, 84, 130],
      ],
      outdoor: [],
      openings: [
        ['d1', 'door', 310, 150], ['d2', 'door', 244, 205], ['d3', 'door', 376, 205], ['d4', 'door', 476, 205],
        ['d5', 'door', 320, 260], ['d6', 'door', 246, 325], ['d7', 'door', 400, 325], ['d8', 'door', 526, 325],
        ['w1', 'window', 200, 150], ['w2', 'window', 420, 150], ['w3', 'window', 543, 150], ['w4', 'window', 160, 325],
        ['w5', 'window', 203, 390], ['w6', 'window', 323, 390], ['w7', 'window', 463, 390], ['w8', 'window', 568, 390],
        ['w9', 'window', 610, 205], ['w10', 'window', 610, 325],
      ],
    },
  };

  const ARCHIVE = 'harbour-block-archive.zip';

  // Every file in the sample archive, in archive order: [path, size, kind, lane, drawing id | null, role or why set aside].
  const FILES = [
    ['plans/floor-01.dxf', '1.2 MB', 'DXF', 'CAD', 'floor-01', 'read'],
    ['model/harbour-block.ifc', '9.6 MB', 'IFC model', 'CAD', 'floor-01', 'second'],
    ['plans/floor-02.dxf', '1.4 MB', 'DXF', 'CAD', 'floor-02', 'read'],
    ['plans/floor-02.pdf', '880 kB', 'Vector PDF', 'CAD', 'floor-02', 'shown'],
    ['plans/floor-02.png', '413 kB', 'PNG scan', 'Vision', 'floor-02', 'second'],
    ['plans/floor-03.dwg', '517 kB', 'DWG', 'CAD', 'floor-03', 'read'],
    ['scans/flat-b12-scan.png', '2.1 MB', 'PNG scan', 'Vision', 'flat-b12', 'read'],
    ['scans/flat-c03-photo.jpg', '38 kB', 'JPG photo', 'Vision', 'flat-c03', 'read'],
    ['scans/ground-floor-scan.jpg', '554 kB', 'JPG scan', 'Vision', 'ground-floor', 'read'],
    ['readme.txt', '2 kB', 'Text', null, null, 'not a drawing'],
    ['__MACOSX/._floor-01.dxf', '4 kB', 'System file', null, null, 'system file, skipped'],
  ].map(([path, size, kind, lane, drawing, role]) => ({ path, size, kind, lane, drawing, role }));

  // Drawings: a layout, extra or changed openings, and the check items: places the readers do not agree on, in the
  // shape of the API's answer.check (#14): mark_id (null: a place a reader saw that the answer did not count), why,
  // readers {reader id: what it says}. Missed places carry their quantity and position.
  const said = (answer, detector, seg) => ({ answer, 'detector-m': detector, seg });
  const DRAWINGS = [
    { id: 'floor-01', name: 'plans/floor-01', layout: 'twoFlats', lane: 'CAD', meta: 'DXF · vector',
      extra: [['d15', 'door', 300, 300, 'c1']], check: [] },
    { id: 'floor-02', name: 'plans/floor-02', layout: 'twoFlats', lane: 'CAD', meta: 'DXF · vector', extra: [], check: [] },
    { id: 'floor-03', name: 'plans/floor-03', layout: 'twoFlats', lane: 'CAD', meta: 'DWG, converted to DXF once',
      extra: [['g1', 'door', 345, 48, 'c2']], check: [] },
    { id: 'flat-b12', name: 'scans/flat-b12-scan', layout: 'flatB', lane: 'Vision', meta: 'PNG scan',
      extra: [['w7', 'window', 0, 63, 'c3']],
      check: [
        { mark_id: 'd6', why: 'Counted, but the detector sees nothing here: the door leaf is faint in the scan.', readers: said('a door', 'nothing', 'a door') },
        { mark_id: null, id: 'x1', quantity: 'door', x: 222, y: 158, why: 'Not counted, but 2 of 3 readers see a door here.', readers: said('nothing', 'a door', 'a door') },
        { mark_id: 'bath', why: 'The outline may be off: a wall line is broken in the scan.', readers: { answer: 'this outline', seg: 'a larger room' } },
      ] },
    { id: 'flat-c03', name: 'scans/flat-c03-photo', layout: 'flatB', lane: 'Vision', meta: 'JPG photo · low resolution',
      extra: [],
      check: [
        { mark_id: 'd3', why: 'Counted, but only 1 of 3 readers sees a door leaf: the photo is low resolution.', readers: said('a door', 'nothing', 'an opening') },
        { mark_id: null, id: 'x1', quantity: 'window', x: 282, y: 40, why: 'Not counted, but 2 of 3 readers see a window here.', readers: said('nothing', 'a window', 'a window') },
        { mark_id: 'w5', why: 'Counted, but it could be a vent: the photo is low resolution.', readers: said('a window', 'a window', 'a vent') },
        { mark_id: 'w6', why: 'Counted, but it could be a vent: the photo is low resolution.', readers: said('a window', 'a window', 'a vent') },
        { mark_id: 'bed2', why: 'The label is not readable, so the room type is a guess.', readers: { answer: 'Bedroom', seg: 'no label' } },
      ] },
    { id: 'ground-floor', name: 'scans/ground-floor-scan', layout: 'groundFloor', lane: 'Vision', meta: 'JPG scan · pencil',
      extra: [],
      check: [
        { mark_id: 'd4', why: 'Counted, but only 1 of 3 readers sees a door here.', readers: said('a door', 'nothing', 'nothing') },
        { mark_id: null, id: 'x1', quantity: 'door', x: 160, y: 205, why: 'Not counted, but 2 of 3 readers see a door here.', readers: said('nothing', 'a door', 'a door') },
        { mark_id: 'w3', why: 'Counted, but it is drawn faintly and may be a niche.', readers: said('a window', 'a window', 'nothing') },
        { mark_id: 'pantry', why: 'The label is smudged, so the room type is a guess.', readers: { answer: 'Pantry', seg: 'no label' } },
      ] },
  ];

  // Conflicts: one element, two readings. kind null = not counted at all.
  const CONFLICTS = [
    { id: 'c1', drawing: 'floor-01', element: 'd15', quantity: 'door', ai: 0,
      title: 'Doors on storey 1', readers: { ifc: 'a door', cad: 'nothing' }, files: 'model/harbour-block.ifc ↔ plans/floor-01.dxf',
      variants: [{ kind: 'door', src: 'IFC model: IfcDoor on storey 1' }, { kind: null, src: 'DXF: DOOR layer of floor-01' }],
      rules: ['A BIM model outranks CAD when both carry the same revision.', 'Both files carry revision C.'],
      why: 'Same revision, so the model wins. The extra door (the stair store) is drawn in the model and missing from the DXF.' },
    { id: 'c2', drawing: 'floor-03', element: 'g1', quantity: 'door', ai: 1,
      title: 'Glazed door on layer A-GLAZ', readers: { cad: 'a window', block: 'a door' }, files: 'plans/floor-03.dwg',
      variants: [{ kind: 'window', label: 'Window', src: 'Layer A-GLAZ, where windows live' },
        { kind: 'door', label: 'Door', src: 'Block has a door leaf and a swing arc' }],
      rules: ['Glazed doors count as doors.', 'An opening with a leaf and a swing is a door, whatever its layer.'],
      why: 'The block has a leaf and a swing arc, so it is a door. The layer name is overruled.' },
    { id: 'c3', drawing: 'flat-b12', element: 'w7', quantity: 'window', ai: null,
      title: 'Is the balcony glazing a window?', readers: { 'detector-m': 'nothing', vision: 'a window' }, files: 'scans/flat-b12-scan.png',
      variants: [{ kind: null, src: 'Detector: glazing is not a window in a wall' }, { kind: 'window', src: 'Vision count: glazing counted as a window' }],
      rules: ['One window per opening in a wall, whatever the number of panes.', 'Balcony glazing on an outdoor railing is not a wall.'],
      why: 'The scan does not show whether the glazing sits in a wall or on the railing. Both readings follow the rules.' },
  ];

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

  const API = { extractFacts, askProject, LAYOUTS, ARCHIVE, FILES, DRAWINGS, CONFLICTS, QUANTITIES, STEPS, drawing, layoutOf, rooms, openings,
    marksFor, valueOf, disputed, parseQuestion, answer, ruleOf, noun, formatValue, variantLabels, crossChecks, progress, readingOf };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.VData = API;
})(typeof window !== 'undefined' ? window : globalThis);
