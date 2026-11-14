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
  const TRIAGE = Object.fromEntries(ARCH.filter((f) => f.triage).map((f) => [f.path, { ...f.triage, image: f.image, credit: f.credit, example: true }]));
  // Hard-coded demo conflicts on the real floor (Tudor, 15:10: "show some conflicts"). Every value is a real one from
  // the answer key; the second reading and the rules show how Conflicts works today. match: the answer-key question it
  // decides (a substring), kind: its quantity.
  const pdf = D.files.find((f) => f.path.endsWith('.pdf')), png = D.files.find((f) => f.path.endsWith('.png'));
  const aptA = keyOf(/apartment A/), indoor = net, doors = keyOf(/How many doors/), stanze = keyOf(/rooms labelled 'Stanza' are/);
  const CONFLICTS = !pdf || !png ? [] : [
    doors !== null && { id: 'c1', drawing: ID, quantity: 'door', match: 'How many doors', ai: 0, title: 'Doors on this floor',
      readers: { 'vector PDF': `${doors} doors`, 'PNG rendering': `${doors - 1} doors` }, files: `${pdf.path} ↔ ${png.path}`,
      variants: [{ kind: 'door', value: doors, label: `${doors} doors`, src: 'Vector PDF: every door symbol, the flat\'s entrance door included' },
        { kind: 'door', value: doors - 1, label: `${doors - 1} doors`, src: 'PNG rendering: the entrance door is drawn on the stair-hall wall and was read as wall' }],
      rules: ['Vector geometry outranks a raster rendering of the same sheet.', 'The flat\'s entrance door counts as a door.'],
      why: `Same sheet in two formats, so the vector PDF wins: ${doors} doors.` },
    aptA !== null && indoor !== null && { id: 'c2', drawing: ID, quantity: 'area', match: 'apartment A', ai: 0, title: 'Net floor area of apartment A',
      readers: { 'room table': `${aptA.toFixed(2)} m²`, 'outline sum': `${indoor.toFixed(2)} m²` }, files: pdf.path,
      variants: [{ kind: 'area', value: aptA, label: `${aptA.toFixed(2)} m²`, src: 'The flat\'s own rooms, balcony left out' },
        { kind: 'area', value: indoor, label: `${indoor.toFixed(2)} m²`, src: 'Every numbered indoor room, the shared stair hall included' }],
      rules: ['A flat\'s area counts only its own rooms.', 'The stair hall (Vano scala) is shared, so it is not part of the flat.'],
      why: `The stair hall belongs to the building, not the flat: ${aptA.toFixed(2)} m².` },
    stanze && stanze > 1 && { id: 'c3', drawing: ID, quantity: 'bedroom', match: null, ai: null, title: 'Bedrooms in apartment A: is one of the rooms the living room?',
      readers: { 'room labels': `${stanze} × 'Stanza'`, 'room types': `${stanze} bedrooms, or ${stanze - 1} and a living room` }, files: pdf.path,
      where: `The ${stanze} rooms labelled 'Stanza' (Italian for room)`,
      variants: [{ kind: 'bedroom', value: stanze, label: `${stanze} bedrooms`, src: `Every room labelled 'Stanza' is a bedroom` },
        { kind: 'bedroom', value: stanze - 1, label: `${stanze - 1} bedrooms + a living room`, src: 'No room is labelled living room (soggiorno), so one Stanza is it, the way Swiss listings count rooms' }],
      rules: ['A bedroom is a habitable room that is not the living room.', `The plan labels all ${stanze} rooms 'Stanza' and none as the living room, so it does not say which one it is.`],
      why: 'Only someone who knows the flat can say whether one of the rooms is the living room. It decides the bedroom count and which building-code room rules apply.',
      placeholder: 'e.g. 3 bedrooms, room 1.02 is the living room',
      suggest: ['3 bedrooms, room 1.02 is the living room', '3 bedrooms and a study', '2 bedrooms, a living room and a study'] },
  ].filter(Boolean);
  // Hard-coded issues on the real files (Tudor, 15:35: things that might actually need a look, not the vision model's)
  const plans = ARCH.filter((f) => f.plan).map((f) => f.path), dxf = D.files.find((f) => f.path.endsWith('.dxf'));
  const ISSUES = [
    plans[1] && { severity: 'needs_person', file: plans[1], why: 'No scale bar or dimension was read on this scan, so areas on it are not measured. Add the scale to measure them.' },
    plans[0] && { severity: 'needs_person', file: plans[0], why: 'Some hand-written room names on this archive plan could not be read, so those rooms have no type.' },
    dxf && { severity: 'note', file: dxf.path, why: 'The same floor as the vector PDF: read once, from the PDF.' },
    png && { severity: 'note', file: png.path, why: 'A rendering of the same floor: used for pictures, not counted again.' },
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

  root.VData = { ...S, ARCHIVE: NAME, FLOOR_ID: D.archive, CREDIT: D.credit, FILES, DRAWINGS, TRIAGE, CONFLICTS, ISSUES, variantLabels: (c) => c.variants.map((v) => v.label), QUANTITIES, SUGGEST, drawing,
    answer, parseQuestion, noun, formatValue, ruleOf, askProject, extractFacts, crossChecks: () => [],
    valueOf: (marks, quantity) => { throw new Error(`no marks in Stoa mode (${quantity})`); } };
})(window);
