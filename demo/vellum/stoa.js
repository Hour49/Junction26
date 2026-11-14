// Stoa mode (local only): builds window.VData from one real Stoa floor (window.VStoaData, written by
// make_stoa_demo.py into the gitignored stoa/ folder). Answers come from the dataset's answer key; the data has no
// positions, so there are no marks, conflicts or cross-checks. Loaded by stoa/index.html only, after data.js and
// stoa/data.js.
(function (root) {
  'use strict';
  const S = root.VData, D = root.VStoaData;  // S: the synthetic demo, for the reading steps and the progress clock
  const ID = 'stoa';

  // "How many doors (…) are drawn" → door/doors; an area question → area
  const quantityOf = (q) => (q.unit === 'm2' ? 'area' : ((q.question.match(/^How many (\w+)/) || [])[1] || 'item').replace(/s$/, ''));
  const QS = D.questions.map((q) => ({ ...q, quantity: quantityOf(q) }));
  const QUANTITIES = { area: { noun: ['m²', 'm²'], rule: 'As the answer key measures it: net floor area, inside the walls.' } };
  for (const q of QS) if (!QUANTITIES[q.quantity]) QUANTITIES[q.quantity] = { noun: [q.quantity, `${q.quantity}s`], rule: 'As the answer key counts them.' };

  // The archive folder (file triage, a preview): real scans, each looked at by eye. A floor plan is a drawing with no
  // answer key; any other kind is set aside, its register row and description handed to triage.js as TRIAGE.
  const ARCH = D.archive_files || [];
  const planId = (i) => `a${i + 1}`;
  const FILES = D.files.map((f) => ({ ...f, drawing: ID })).concat(ARCH.map((f, i) => ({ ...f, drawing: f.plan ? planId(i) : null })));
  const image = FILES.find((f) => f.image).image;
  // A plain-English name from the answer key, instead of the dataset id (site…_bldg…_floor…)
  const keyOf = (re) => { const q = QS.find((x) => re.test(x.question)); return q ? q.answer : null; };
  const flats = keyOf(/apartments/), net = keyOf(/total net floor area/);
  const NAME = `Swiss apartment floor${flats ? `, ${flats} flat${flats === 1 ? '' : 's'}` : ''}${net ? `, ${Math.round(net)} m²` : ''}`;
  const DRAWINGS = [{ id: ID, name: NAME, lane: 'CAD', meta: D.files.map((f) => f.kind).join(' · '), image, check: [] }]
    .concat(ARCH.map((f, i) => (f.plan ? { id: planId(i), name: f.path.split('/').pop(), lane: 'Vision', meta: `${f.kind} · no answer key`, image: f.image, credit: f.credit, check: [] } : null)).filter(Boolean));
  // The house set (OpeningDesign): real sheets of one house; its plan is a drawing, the elevations and section are
  // other sheets of the same set. COMBINED: questions answered from several of them, read by eye (no answer key).
  const HOUSE = D.house_files || [], hp = HOUSE.find((f) => f.sheet === 'floor_plan');
  if (hp) {
    DRAWINGS.push({ id: 'house', name: 'House with a new second floor', lane: 'CAD', meta: 'Vector PDF · no answer key', image: hp.image, check: [] });
    for (const f of HOUSE) FILES.push({ ...f, lane: 'CAD', role: f.sheet === 'floor_plan' ? 'source' : 'sheet', drawing: 'house' });
  }
  const sheet = (word) => (HOUSE.find((f) => f.path.includes(word)) || {}).path;
  const COMBINED = !hp ? [] : [
    { q: 'How many storeys does the house have, and how many bathrooms are on its first floor?', keys: [/stor(e)?y/, /bath/],
      lead: '2 storeys above ground and a basement. 1 bathroom on the first floor.',
      refs: [[sheet('SOUTH'), 'Levels on the elevation: basement −7′-8″, 1st floor 0′-0″, 2nd floor 9′-0″, roof 16′-10″.'],
        [sheet('SECTION'), 'North–south section looking west: the same levels, and the stair up to the new second floor.'],
        [hp.path, 'One bathtub and one toilet on the first floor: one bathroom.']] },
    { q: 'How many windows face south?', keys: [/window/, /south/],
      lead: '7 windows face south: 4 upstairs and 3 downstairs, plus the front door.',
      refs: [[sheet('SOUTH'), 'Upstairs windows 16, 18, 16, 16; downstairs 19, 19, 20; the front door is door 1.'],
        [sheet('EAST'), 'The house from the east.'], [sheet('WEST'), 'The house from the west.'], [sheet('NORTH'), 'The house from the north.']] },
    { q: 'How tall is the house?', keys: [/tall|height|high/],
      lead: '25′-9″ from the ground to the top of the roof.',
      refs: [[sheet('SOUTH'), 'Dimension on the south elevation: 25′-9″, ground to the top of the roof.'], [sheet('SECTION'), 'North–south section looking west: roof at 16′-10″ over the second floor at 9′-0″.']] },
  ];
  for (const c of COMBINED) c.refs = c.refs.filter(([path]) => path);
  const combinedFor = (text) => { const t = text.toLowerCase(); return COMBINED.find((c) => c.keys.every((k) => k.test(t))) || null; };
  const TRIAGE = Object.fromEntries(ARCH.filter((f) => f.triage).map((f) => [f.path, { ...f.triage, image: f.image, credit: f.credit, example: true }]));
  // Hard-coded demo conflicts on the real floor (Tudor, 15:10: "show some conflicts"). Every value is a real one from
  // the answer key; the second reading and the rules show how Conflicts works today. match: the answer-key question it
  // decides (a substring), kind: its quantity.
  const pdf = D.files.find((f) => f.path.endsWith('.pdf')), png = D.files.find((f) => f.path.endsWith('.png'));
  const aptA = keyOf(/apartment A/), indoor = net, doors = keyOf(/How many doors/), stanze = keyOf(/rooms labelled 'Stanza' are/);
  // src: where each conflict and issue sits on its real source image, placed by eye. files: the images (the first is
  // shown in the card), view: the crop shown and box: the place in question, both in % of the image (x, y, w, h);
  // ratio: the image's width / height. The floor sits in the middle of an A3 sheet, so its crop is FLOOR.
  const A3 = 1600 / 1131, FLOOR = [31, 22, 38, 42];
  const floorSrc = (files, marks) => ({ files, view: FLOOR, ratio: A3, marks });
  const CONFLICTS = !pdf || !png ? [] : [
    doors !== null && { id: 'c1', drawing: ID, quantity: 'door', match: 'How many doors', ai: 0, title: 'Doors on this floor',
      readers: { 'vector PDF': `${doors} doors`, 'PNG rendering': `${doors - 1} doors` }, files: `${pdf.path} ↔ ${png.path}`,
      variants: [{ kind: 'door', value: doors, label: `${doors} doors`, src: 'Vector PDF: every door symbol, the flat\'s entrance door included' },
        { kind: 'door', value: doors - 1, label: `${doors - 1} doors`, src: 'PNG rendering: the entrance door is drawn on the stair-hall wall and was read as wall' }],
      rules: ['Vector geometry outranks a raster rendering of the same sheet.', 'The flat\'s entrance door counts as a door.'],
      why: `Same sheet in two formats, so the vector PDF wins: ${doors} doors.`,
      src: floorSrc([pdf.path, png.path], [{ box: [44.8, 30, 4.2, 5], label: 'The flat\'s entrance door, on the stair-hall wall' }]) },
    aptA !== null && indoor !== null && { id: 'c2', drawing: ID, quantity: 'area', match: 'apartment A', ai: 0, title: 'Net floor area of apartment A',
      readers: { 'room table': `${aptA.toFixed(2)} m²`, 'outline sum': `${indoor.toFixed(2)} m²` }, files: pdf.path,
      variants: [{ kind: 'area', value: aptA, label: `${aptA.toFixed(2)} m²`, src: 'The flat\'s own rooms, balcony left out' },
        { kind: 'area', value: indoor, label: `${indoor.toFixed(2)} m²`, src: 'Every numbered indoor room, the shared stair hall included' }],
      rules: ['A flat\'s area counts only its own rooms.', 'The stair hall (Vano scala) is shared, so it is not part of the flat.'],
      why: `The stair hall belongs to the building, not the flat: ${aptA.toFixed(2)} m².`,
      src: floorSrc([pdf.path], [{ box: [39.4, 25.5, 9.2, 9.3], label: 'The stair hall (Vano scala 1.10), shared by the building' }]) },
    stanze && stanze > 1 && { id: 'c3', drawing: ID, quantity: 'bedroom', match: null, ai: null, title: 'Bedrooms in apartment A: is one of the rooms the living room?',
      readers: { 'room labels': `${stanze} × 'Stanza'`, 'room types': `${stanze} bedrooms, or ${stanze - 1} and a living room` }, files: pdf.path,
      where: `The ${stanze} rooms labelled 'Stanza' (Italian for room)`,
      variants: [{ kind: 'bedroom', value: stanze, label: `${stanze} bedrooms`, src: `Every room labelled 'Stanza' is a bedroom` },
        { kind: 'bedroom', value: stanze - 1, label: `${stanze - 1} bedrooms + a living room`, src: 'No room is labelled living room (soggiorno), so one Stanza is it, the way Swiss listings count rooms' }],
      rules: ['A bedroom is a habitable room that is not the living room.', `The plan labels all ${stanze} rooms 'Stanza' and none as the living room, so it does not say which one it is.`],
      why: 'Only someone who knows the flat can say whether one of the rooms is the living room. It decides the bedroom count and which building-code room rules apply.',
      placeholder: 'e.g. 3 bedrooms, room 1.02 is the living room',
      src: floorSrc([pdf.path], [['1.02', [58.2, 25.8, 7.4, 14.5]], ['1.06', [55.8, 40.3, 9.8, 9.9]], ['1.07', [39.4, 46.9, 12.9, 12.8]], ['1.08', [52.4, 49.9, 13.1, 9.8]]]
        .map(([n, box]) => ({ box, label: `Stanza ${n}` }))),
      suggest: ['3 bedrooms, room 1.02 is the living room', '3 bedrooms and a study', '2 bedrooms, a living room and a study'] },
  ].filter(Boolean);
  // Hard-coded issues on the real files (Tudor, 15:35: things that might actually need a look, not the vision model's)
  const plans = ARCH.filter((f) => f.plan).map((f) => f.path), dxf = D.files.find((f) => f.path.endsWith('.dxf'));
  // A person answers a needs_person issue on Documents; a note is only shown (and not counted on the tab).
  const ISSUES = [
    plans[1] && { id: 'i1', severity: 'needs_person', file: plans[1], why: 'No scale bar or dimension was read on this scan, so areas on it are not measured. Add the scale to measure them.',
      src: { files: [plans[1]], view: [0, 0, 100, 100], ratio: 931 / 537, marks: [{ box: [20, 0, 57, 10], label: 'The title gives no scale, and no dimension is written on the plan' }] },
      placeholder: 'e.g. 1/8 inch to 1 foot', suggest: ['1/8 inch to 1 foot (1:96)', '1/16 inch to 1 foot (1:192)', 'Leave it unmeasured'] },
    plans[0] && { id: 'i2', severity: 'needs_person', file: plans[0], why: 'Some hand-written room names on this archive plan could not be read, so those rooms have no type.',
      src: { files: [plans[0]], view: [0, 0, 100, 100], ratio: A3, marks: [{ box: [34.2, 30.6, 8.4, 5.4], label: '“V.c”?' }, { box: [74.5, 34.6, 9.5, 5], label: '“Dom.”?' }] },
      placeholder: 'e.g. V.c is a WC', suggest: ['V.c is a WC, Dom. is a maid\'s room', 'Leave those rooms without a type'] },
    dxf && { id: 'i3', severity: 'note', file: dxf.path, why: 'The same floor as the vector PDF: read once, from the PDF.' },
    png && { id: 'i4', severity: 'note', file: png.path, why: 'A rendering of the same floor: used for pictures, not counted again.',
      src: floorSrc([png.path], [{ box: [32.5, 24.5, 35.5, 37], label: 'The same floor as the vector PDF' }]) },
  ].filter(Boolean);
  const conflictFor = (q) => CONFLICTS.find((c) => c.match && q.question.includes(c.match)) || null;

  const drawing = (id) => {
    const d = DRAWINGS.find((x) => x.id === id);
    if (!d) throw new Error(`no drawing ${id}`);
    return d;
  };

  // shortcut: word match against the answer key, no parser; exact text first, else the one key question holding every
  // content word of the question (plurals folded). Several or none → no answer, with the candidates as suggestions.
  const STOP = new Set('how many what is the are there this that on of in an and floor plan drawn shown total all do does its it in m² m2 sq'.split(' '));
  const words = (t) => (t.toLowerCase().match(/[\p{L}\p{N}.]+/gu) || []).map((w) => w.replace(/\.$/, '').replace(/s$/, '')).filter((w) => w && !STOP.has(w));  // one letter stays: apartment B
  function match(question) {
    const t = question.trim().toLowerCase();
    const exact = QS.find((q) => q.question.toLowerCase() === t);
    if (exact) return { q: exact, near: [] };
    const want = words(question);
    const near = want.length ? QS.filter((q) => { const have = new Set(words(q.question)); return want.every((w) => have.has(w)); }) : [];
    if (near.length > 1) {  // "the total / whole floor area" means the one total question; else a unique substring
      const core = t.replace(/^(what is|what's|how big is)\s+(the\s+)?/, '').replace(/[?.\s]+$/, '');
      const sub = near.filter((q) => q.question.toLowerCase().includes(core));
      const total = /\b(total|whole|entire|all)\b/.test(t) ? near.filter((q) => /\btotal\b/i.test(q.question)) : [];
      const one = sub.length === 1 ? sub : total.length === 1 ? total : null;
      if (one) return { q: one[0], near };
    }
    return near.length === 1 ? { q: near[0], near } : { q: null, near };
  }

  function answer(drawingId, question, picks) {
    const d = drawing(drawingId), m = match(question);
    if (d.id !== ID) return { drawing: d.id, question, quantity: null, near: [], refusal: 'The answer key has no questions about this drawing, so there is no number to give.' };
    if (!m.q) {
      return { drawing: d.id, question, quantity: null, near: m.near.map((q) => q.question),
        refusal: m.near.length ? `The answer key has ${m.near.length} questions like this${m.near.length > 4 ? '; here are 4 of them' : ''}. Pick one.` : 'The answer key for this floor has no question like this, so there is no number to give.' };
    }
    const c = conflictFor(m.q), pick = c && picks ? picks[c.id] : undefined;
    const value = typeof pick === 'number' ? c.variants[pick].value : pick && pick.custom && !Number.isNaN(parseFloat(pick.custom)) ? parseFloat(pick.custom) : m.q.answer;
    return { drawing: d.id, question, quantity: m.q.quantity, refusal: null, marks: [], rooms: [], value, check: null,
      key: !c, keyQuestion: m.q.question, conflict: c ? c.id : null };
  }
  const parseQuestion = (text) => { const m = match(text); return m.q ? m.q.quantity : null; };

  const noun = (quantity, value) => QUANTITIES[quantity].noun[value === 1 ? 0 : 1];
  const formatValue = (quantity, value) => (quantity === 'area' ? `${value.toFixed(2)} m²` : `${value} ${noun(quantity, value)}`);
  const ruleOf = (a) => QUANTITIES[a.quantity].rule;
  const SUGGEST = ['many doors', 'area of apartment', 'many windows', 'total net floor area', 'many toilets'].map((k) => QS.find((q) => q.question.includes(k)))
    .filter(Boolean).map((q) => q.question);

  // one drawing has an answer key, so an answer is its value as the total (#14 rule); the archive's plans refuse
  function askProject(question, picks) {
    const a = answer(ID, question, picks), part = { drawing_id: ID, name: NAME, answer: a };
    const rest = DRAWINGS.slice(1).map((d) => ({ drawing_id: d.id, name: d.name, answer: answer(d.id, question) }));
    if (a.refusal) return { question, parts: [part, ...rest], total: null, total_unit: null, total_sure: false, total_note: 'No drawing can answer this.', canAnswer: (a.near.length ? a.near : SUGGEST).slice(0, 4) };
    return { question, parts: [part, ...rest], total: a.value, total_unit: a.quantity === 'area' ? 'm2' : 'count', total_sure: false,
      total_note: a.conflict ? 'As settled in Conflicts.' : `From the answer key of ${NAME}.`, canAnswer: null };
  }

  // the Extract panel: rooms per label and the door and window counts, as the answer key gives them
  const keyCount = (word) => { const q = QS.find((x) => x.quantity === word); return q ? q.answer : 0; };
  function extractFacts() {
    const rooms = [];
    for (const q of QS) {
      const label = (q.question.match(/rooms labelled '(.+)'/) || [])[1];
      if (label && q.quantity === 'room') for (let i = 0; i < q.answer; i++) rooms.push({ label });
    }
    return { drawing: DRAWINGS[0], rooms, doors: keyCount('door'), windows: keyCount('window') };
  }

  root.VData = { ...S, ARCHIVE: NAME, FLOOR_ID: D.archive, CREDIT: D.credit, FILES, DRAWINGS, TRIAGE, CONFLICTS, ISSUES, COMBINED, combinedFor, variantLabels: (c) => c.variants.map((v) => v.label), QUANTITIES, SUGGEST, drawing,
    answer, parseQuestion, noun, formatValue, ruleOf, askProject, extractFacts, crossChecks: () => [],
    valueOf: (marks, quantity) => { throw new Error(`no marks in Stoa mode (${quantity})`); } };
})(window);
