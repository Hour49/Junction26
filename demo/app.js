'use strict';
/* Countersign mock. Static, no build step, no network. Everything shown is synthetic:
   the two floor plans are drawn from the data below, and counts and areas are computed from that same data. */

const S = 50; // drawing units per metre
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const eur = (v) => '€' + v.toFixed(v < 0.01 && v > 0 ? 5 : 4);

/* ------------------------------------------------------------------ plans */

function mirrorApt(apt, W, from, to) {
  const re = (s) => s.replace(new RegExp('^' + from), to);
  return {
    rooms: apt.rooms.map((r) => ({ ...r, id: re(r.id), apt: to, x: W - r.x - r.w, lx: r.lx && W - r.lx })),
    doors: apt.doors.map((d) => ({
      ...d, id: re(d.id), x: W - d.x,
      swing: d.wall === 'v' ? -d.swing : d.swing, hinge: d.wall === 'h' ? -d.hinge : d.hinge,
    })),
    windows: apt.windows.map((w) => ({ ...w, id: re(w.id), x: W - w.x })),
    fixtures: apt.fixtures.map((f) => ({ ...f, id: re(f.id), x: W - f.x })),
  };
}

function planA() {
  const a = {
    rooms: [
      { id: 'A1', name: 'Living', x: 0, y: 0, w: 5, h: 5.5 },
      { id: 'A2', name: 'Kitchen', x: 5, y: 0, w: 3.5, h: 3.2 },
      { id: 'A3', name: 'Corridor', x: 5, y: 3.2, w: 3.5, h: 2.3 },
      { id: 'A4', name: 'Bedroom', x: 0, y: 5.5, w: 4.2, h: 4.5 },
      { id: 'A5', name: 'Bath', x: 4.2, y: 5.5, w: 2.3, h: 2.6, lx: 5.8, ly: 6.75 },
      { id: 'A6', name: 'Storage', x: 6.5, y: 5.5, w: 2, h: 2.6 },
      { id: 'A7', name: 'Study', x: 4.2, y: 8.1, w: 4.3, h: 1.9 },
      { id: 'A8', name: 'Balcony', x: 0, y: 10, w: 4.2, h: 1.2, kind: 'out' },
    ].map((r) => ({ kind: 'in', apt: 'A', ...r })),
    doors: [
      { id: 'Ad1', name: 'Entrance, corridor to stair', wall: 'v', x: 8.5, y: 4.4, swing: -1, hinge: 1 },
      { id: 'Ad2', name: 'Living to corridor', wall: 'v', x: 5, y: 4.4, swing: -1, hinge: -1 },
      { id: 'Ad3', name: 'Kitchen to corridor', wall: 'h', x: 6.6, y: 3.2, open: true },
      { id: 'Ad4', name: 'Bedroom to living', wall: 'h', x: 2, y: 5.5, swing: 1, hinge: 1 },
      { id: 'Ad5', name: 'Bath to corridor', wall: 'h', x: 5.9, y: 5.5, swing: 1, hinge: -1 },
      { id: 'Ad6', name: 'Storage to corridor', wall: 'h', x: 7.5, y: 5.5, swing: 1, hinge: 1 },
      { id: 'Ad7', name: 'Study to bedroom', wall: 'v', x: 4.2, y: 9.1, swing: 1, hinge: 1 },
      { id: 'Ad8', name: 'Balcony door', wall: 'h', x: 2, y: 10, swing: -1, hinge: 1 },
    ],
    windows: [
      { id: 'Aw1', name: 'Living, north', wall: 'h', x: 1.5, y: 0 },
      { id: 'Aw2', name: 'Living, north', wall: 'h', x: 3.6, y: 0 },
      { id: 'Aw3', name: 'Living, side', wall: 'v', x: 0, y: 2.8 },
      { id: 'Aw4', name: 'Kitchen', wall: 'h', x: 6.8, y: 0 },
      { id: 'Aw5', name: 'Bedroom, side', wall: 'v', x: 0, y: 7.6 },
      { id: 'Aw6', name: 'Study', wall: 'h', x: 6.4, y: 10 },
    ],
    fixtures: [
      { id: 'Af1', type: 'bath', name: 'Bathtub', x: 4.68, y: 7.1, rot: 0 },
      { id: 'Af2', type: 'wc', name: 'WC', x: 6.1, y: 7.62, rot: 180 },
      { id: 'Af3', type: 'basin', name: 'Washbasin', x: 5.35, y: 7.82, rot: 0 },
      { id: 'Af4', type: 'sink', name: 'Kitchen sink', x: 7.8, y: 0.42, rot: 0 },
    ],
  };
  const b = mirrorApt(a, 20, 'A', 'B');
  b.doors.find((d) => d.id === 'Bd2').double = true;
  return {
    id: 'A', file: 'plans/floor-02', title: 'Floor 2, two apartments', route: 'vector',
    caption: 'Source: DXF. Shown on its PDF rendering. Coordinates are real-world metres, so the scale is exact.',
    minX: 0, minY: 0, W: 20, H: 11.2,
    rooms: [...a.rooms, { id: 'S1', name: 'Stair', x: 8.5, y: 0, w: 3, h: 10, kind: 'in', apt: null }, ...b.rooms],
    doors: [...a.doors, ...b.doors],
    windows: [...a.windows, { id: 'Sw1', name: 'Stair', wall: 'h', x: 10, y: 0 }, ...b.windows],
    fixtures: [...a.fixtures, ...b.fixtures],
  };
}

function planB() {
  return {
    id: 'B', file: 'scans/flat-b12-scan', title: 'Flat B12, scanned sheet', route: 'raster', scan: true,
    caption: 'Source: PNG scan, 1240×1754 px. Rotated 180° at ingest. Scale 1:100 read from the scale bar, ±1.5%.',
    minX: -1.4, minY: 0, W: 9.4, H: 8,
    rooms: [
      { id: 'R1', name: 'OH', x: 0, y: 0, w: 4.8, h: 4.6 },
      { id: 'R2', name: 'K', x: 4.8, y: 0, w: 3.2, h: 3 },
      { id: 'R3', name: 'ET', x: 4.8, y: 3, w: 3.2, h: 1.6 },
      { id: 'R4', name: 'MH', x: 0, y: 4.6, w: 3.4, h: 3.4 },
      { id: 'R5', name: 'MH', x: 3.4, y: 4.6, w: 2.6, h: 3.4 },
      { id: 'R6', name: 'KH', x: 6, y: 4.6, w: 2, h: 2, lx: 7.55, ly: 5.85 },
      { id: 'R7', name: 'S', x: 6, y: 6.6, w: 2, h: 1.4, lx: 7.4 },
      { id: 'R8', name: 'PARVEKE', x: -1.4, y: 0.6, w: 1.4, h: 3, kind: 'out' },
    ].map((r) => ({ kind: 'in', apt: 'B12', ...r })),
    doors: [
      { id: 'd1', name: 'Entrance', wall: 'v', x: 8, y: 3.8, swing: -1, hinge: 1 },
      { id: 'd2', name: 'OH to ET', wall: 'v', x: 4.8, y: 3.8, swing: -1, hinge: -1 },
      { id: 'd3', name: 'K to ET', wall: 'h', x: 6.4, y: 3, open: true },
      { id: 'd4', name: 'MH to OH', wall: 'h', x: 1.5, y: 4.6, swing: 1, hinge: 1 },
      { id: 'd5', name: 'MH to ET', wall: 'h', x: 5.4, y: 4.6, swing: 1, hinge: -1 },
      { id: 'd6', name: 'KH to ET', wall: 'h', x: 6.6, y: 4.6, swing: 1, hinge: -1 },
      { id: 'd7', name: 'S to KH', wall: 'h', x: 6.5, y: 6.6, swing: 1, hinge: 1, small: true },
      { id: 'd8', name: 'Balcony door', wall: 'v', x: 0, y: 2.9, swing: -1, hinge: 1 },
    ],
    windows: [
      { id: 'w1', name: 'OH, top wall', wall: 'h', x: 2.4, y: 0 },
      { id: 'w2', name: 'K, top wall', wall: 'h', x: 6.4, y: 0 },
      { id: 'w3', name: 'OH, beside the balcony door', wall: 'v', x: 0, y: 1.5 },
      { id: 'w4', name: 'MH, side wall', wall: 'v', x: 0, y: 6.3 },
      { id: 'w5', name: 'MH, bottom wall', wall: 'h', x: 1.7, y: 8 },
      { id: 'w6', name: 'MH, bottom wall', wall: 'h', x: 4.7, y: 8 },
      { id: 'w7', name: 'Balcony glazing', wall: 'v', x: -1.4, y: 2.1, len: 2.2, contested: true },
    ],
    fixtures: [
      { id: 'f1', type: 'wc', name: 'WC', x: 7.62, y: 5.2, rot: 90 },
      { id: 'f2', type: 'basin', name: 'Washbasin', x: 7.3, y: 6.36, rot: 180 },
      { id: 'f3', type: 'shower', name: 'Shower', x: 6.45, y: 6.15, rot: 0 },
      { id: 'f4', type: 'sink', name: 'Kitchen sink', x: 7.3, y: 0.42, rot: 0 },
    ],
  };
}

/* ------------------------------------------------------------- quantities */

const center = (r) => ({ x: r.x + r.w / 2, y: r.y + r.h / 2 });
const area = (r) => r.w * r.h;

function countQ(o, marks) {
  return { kind: 'count', signed: null, ...o, marks: marks.map((m) => ({ orig: m.state, ...m })) };
}
function areaQ(o, parts) {
  return { kind: 'area', unit: 'm²', signed: null, ...o, parts: parts.map((p) => ({ orig: p.inc, ...p })) };
}
const mark = (it, state, note) => ({ id: it.id, x: it.x, y: it.y, name: it.name, state: state || 'counted', note: note || '' });
const part = (r, inc, why) => ({ id: r.id, name: r.name, area: area(r), inc, why: why || '' });

function buildQuantities(p) {
  const vec = p.route === 'vector';
  const m1 = vec ? 'Geometry: DXF layers and blocks' : 'Detector and OCR on the scan';
  const m2 = 'Second count: small vision model on the rendering';
  const fx = (types) => p.fixtures.filter((f) => types.includes(f.type)).map((f) => mark(f));
  const roomMarks = (names) => p.rooms.filter((r) => names.includes(r.name)).map((r) => mark({ ...r, ...center(r), name: `${r.id} labelled "${r.name}"` }));
  const q = {};
  q.doors = countQ({ key: 'doors', label: 'Doors', unit: 'doors', method: m1, alt: m2,
    query: 'count(openings where kind = door and has_leaf)',
    rule: 'A doorway fitted with a door counts once, a double door too. Open doorways without a door are not counted.' },
    p.doors.map((d) => mark(d, d.open ? 'excluded' : 'counted', d.open ? 'open doorway, no door leaf drawn' : d.double ? 'double door, counts once' : '')));
  q.windows = countQ({ key: 'windows', label: 'Windows', unit: 'windows', method: m1, alt: m2,
    query: 'count(openings where kind = window)',
    rule: 'One window per opening in a wall, whatever the number of panes. Glazed doors count as doors.' },
    p.windows.map((w) => mark(w, w.contested ? 'contested' : 'counted',
      w.contested ? 'The detector reads this as balcony glazing, not a window in a wall. The vision count includes it.' : '')));
  q.wc = countQ({ key: 'wc', label: 'Toilets (WC)', unit: 'toilets', method: m1, alt: m2,
    query: 'count(fixtures where type = wc)', rule: 'One per toilet bowl symbol.' }, fx(['wc']));
  q.basins = countQ({ key: 'basins', label: 'Sinks and washbasins', unit: 'sinks and basins', method: m1, alt: m2,
    query: 'count(fixtures where type in (basin, sink))',
    rule: 'Kitchen and bathroom together. A double-bowl sink counts once.' }, fx(['basin', 'sink']));
  q.baths = countQ({ key: 'baths', label: 'Baths and showers', unit: 'baths and showers', method: m1, alt: m2,
    query: 'count(fixtures where type in (bath, shower))', rule: 'One per bathtub or shower symbol.' }, fx(['bath', 'shower']));
  const bed = vec ? 'Bedroom' : 'MH';
  q.bedrooms = countQ({ key: 'bedrooms', label: `Bedrooms (label "${bed}")`, unit: 'bedrooms',
    method: vec ? 'Text: room labels in the DXF' : 'OCR of room labels', alt: m2,
    query: `count(rooms where label = "${bed}")`,
    rule: `Rooms whose label reads "${bed}". A room without a label is never guessed to be a bedroom.` }, roomMarks([bed]));
  if (vec) {
    q.apartments = countQ({ key: 'apartments', label: 'Apartments', unit: 'apartments', method: 'Geometry: unit outlines and unit labels', alt: m2,
      query: 'count(units)', rule: 'One per residential unit. The stair core is common area, not a unit.' },
      ['A', 'B'].map((a) => { const r = p.rooms.find((x) => x.id === a + '3'); return mark({ id: 'apt' + a, ...center(r), name: 'Apartment ' + a }); }));
    const indoor = (r) => r.kind !== 'out';
    q.areaFloor = areaQ({ key: 'areaFloor', label: 'Net floor area, whole floor', method: 'Geometry: room polygons from the DXF', alt: 'Check: sum of rooms against the floor outline',
      query: 'sum(area(rooms where indoor))', rule: 'All indoor rooms on the floor, the stair included. Balconies are left out.' },
      p.rooms.map((r) => part(r, indoor(r), indoor(r) ? '' : 'balcony, outdoor')));
    for (const a of ['A', 'B']) {
      q['area' + a] = areaQ({ key: 'area' + a, label: `Net floor area, apartment ${a}`, method: 'Geometry: room polygons from the DXF', alt: 'Check: sum of rooms against the unit outline',
        query: `sum(area(rooms where unit = ${a} and indoor))`, rule: `All rooms of apartment ${a} except its balcony. Common areas are left out.` },
        p.rooms.filter((r) => r.apt === a).map((r) => part(r, indoor(r), indoor(r) ? '' : 'balcony, outdoor')));
    }
  } else {
    q.saunas = countQ({ key: 'saunas', label: 'Saunas (label "S")', unit: 'saunas', method: 'OCR of room labels', alt: m2,
      query: 'count(rooms where label = "S")', rule: 'Rooms whose label reads S or SAUNA.' }, roomMarks(['S']));
    q.areaFloor = areaQ({ key: 'areaFloor', label: 'Floor area of the flat', method: 'Room polygons from wall segmentation, scaled by the scale bar', alt: 'Check: two dimension strings on the sheet',
      query: 'sum(area(rooms where indoor))', rule: 'All indoor rooms. The balcony (PARVEKE) is left out.',
      flag: 'The scale comes from a drawn scale bar: ±1.5%. Areas must be within 2%, so confirm one dimension before signing.' },
      p.rooms.map((r) => part(r, r.kind !== 'out', r.kind !== 'out' ? '' : 'balcony, outdoor')));
  }
  for (const k of Object.keys(q)) {
    q[k].altValue = k === 'windows' && !vec ? value(q[k]) + 1 : value(q[k]);
    q[k].origValue = value(q[k]);
  }
  return q;
}

function value(q) {
  if (q.kind === 'count') return q.marks.filter((m) => m.state === 'counted' || m.state === 'added').length;
  return q.parts.filter((p) => p.inc).reduce((s, p) => s + p.area, 0);
}
const fmt = (q, v = value(q)) => (q.kind === 'count' ? String(v) : v.toFixed(2));
const contested = (q) => q.kind === 'count' && q.marks.some((m) => m.state === 'contested');
const edited = (q) => (q.kind === 'count' ? q.marks.some((m) => m.state !== m.orig) : q.parts.some((p) => p.inc !== p.orig));
function status(q) {
  if (q.signed) return ['ok', 'signed off'];
  if (contested(q)) return ['warn', 'methods disagree'];
  if (q.flag) return ['warn', 'check scale'];
  if (edited(q)) return ['info', 'edited'];
  return ['mute', '2 methods agree'];
}

const PLANS = {};
for (const p of [planA(), planB()]) { p.q = buildQuantities(p); PLANS[p.id] = p; }

const SUGGEST = {
  A: [
    'How many doors are on this floor?',
    'What is the net floor area of apartment A, without the balcony?',
    'Wie viele Fenster hat dieses Geschoss?',
    'How many sinks and washbasins are there?',
    'What is the total indoor floor area of this floor?',
    'What fire rating do the stair doors need?',
  ],
  B: [
    'Montako ikkunaa tässä pohjakuvassa on?',
    'How many doors does this flat have?',
    'How many bedrooms (MH) are there?',
    'Is there a sauna?',
    'What is the floor area of this flat?',
  ],
};
const MATCH = [
  [/fire|rating|\bEI ?\d/i, null],
  [/apartment a\b|wohnung a\b/i, 'areaA'], [/apartment b\b|wohnung b\b/i, 'areaB'],
  [/area|pinta-ala|fläche|m2|m²/i, 'areaFloor'],
  [/apartment|wohnung|asunto/i, 'apartments'],
  [/bedroom|makuu|\bmh\b|schlaf/i, 'bedrooms'], [/sauna/i, 'saunas'],
  [/door|ovi|ovea|tür/i, 'doors'], [/window|ikkun|fenster/i, 'windows'],
  [/toilet|\bwc\b|bowl/i, 'wc'], [/basin|sink|lavabo|allas/i, 'basins'], [/bath|shower|suihku|kylpy|dusch/i, 'baths'],
];
const PARSE_COST = 0.00002;

/* ----------------------------------------------------------------- ingest */

const STAGES = [
  { id: 'unpack', name: 'Unpack', cost: 'CPU only',
    what: 'The archive is read entry by entry into a quarantine folder. Nothing is trusted because it came in a zip.',
    how: ['Each entry path is checked so it cannot write outside the target folder.', 'Size caps per file and for the whole archive stop zip bombs.', 'Every file gets a SHA-256 hash. The hash is the cache key: a file ingested before is never ingested twice, in this project or any other.'],
    out: 'An inventory: path, size, hash.', fail: 'A corrupt entry is listed with its error. The other files continue.' },
  { id: 'identify', name: 'Identify', cost: 'CPU only',
    what: 'Work out what each file really is and which files are the same drawing.',
    how: ['The type comes from the first bytes of the file, not from the extension.', 'Files with the same name and a different extension (floor-02.dxf, .pdf, .png) are one drawing in three renderings.', 'Exact copies are collapsed by hash.', 'Encrypted PDFs are tried with an empty password. Photos, thumbnails and office files are set aside with the reason.'],
    out: 'Documents, each with its renderings. A list of what was set aside and why.', fail: 'An unknown type is set aside, never guessed.' },
  { id: 'route', name: 'Route', cost: 'CPU only',
    what: 'Pick, per drawing, the cheapest source that carries the most structure.',
    how: ['Order of preference: BIM model (IFC), then CAD (DXF, DWG), then vector PDF or SVG, then raster scan.', 'The other renderings are kept: one to show evidence on, one for the independent second count.', 'DWG is converted to DXF once. A PDF is tested for real vector content, since many PDFs are a scan in a wrapper.'],
    out: 'One route per drawing: model, vector, raster or text only.', fail: 'If the preferred source fails to parse, the next one down is used and the downgrade is recorded.' },
  { id: 'normalise', name: 'Normalise', cost: 'Raster: small GPU model',
    what: 'Make every sheet upright, split into views, with a known scale.',
    how: ['Orientation: text direction votes for 0, 90, 180 or 270 degrees. Scans are deskewed.', 'A sheet with several views (plan, sections, elevations) is split. Questions are answered per view.', 'Scale, in order of trust: CAD units, a written scale (1:100), a drawn scale bar, dimension strings. The uncertainty is stored with it.'],
    out: 'Upright views, each with a type, a scale and a scale uncertainty.', fail: 'No scale found: counts still work, lengths and areas are refused with that reason.' },
  { id: 'extract', name: 'Extract', cost: 'Raster: detector + OCR',
    what: 'Read the building elements. This is the only stage that differs much by route.',
    how: ['Model: IFC entities and quantity sets (spaces, doors, windows, walls).', 'Vector: layers and blocks give walls, openings, fixtures and text. Rooms are closed from wall loops.', 'Raster: a symbol detector for doors, windows and fixtures, OCR for room labels, wall segmentation for room polygons.', 'Every element keeps the region of the sheet it was read from.'],
    out: 'Raw elements with positions, labels and confidence.', fail: 'Low resolution or no plan view: the affected quantities are marked unavailable instead of guessed.' },
  { id: 'model', name: 'Drawing model', cost: 'CPU only',
    what: 'Write one schema for all routes. Questions only ever read this.',
    how: ['Views, rooms (polygon, label, area), openings (kind, leaf or not, number of leaves), fixtures, units.', 'Every element carries its source region, the method that found it and a confidence.', 'Counting rules live here as data: what counts as a door, what is left out of a net area.'],
    out: 'drawing-model.json per drawing, a few kB.', fail: 'Elements that break the schema are kept in a rejects list, visible to the surveyor.' },
  { id: 'crosscheck', name: 'Cross-check', cost: 'One small vision call per quantity',
    what: 'Count everything a second, independent way, once, at ingest.',
    how: ['A small vision model counts each quantity on the rendering. It never sees the first result.', 'Agreement raises confidence. Disagreement flags the exact marks that differ as contested, for the surveyor.', 'Arithmetic checks: room areas against the unit outline, values against similar drawings.'],
    out: 'A confidence per quantity and a review queue.', fail: 'Contested quantities are answered with both numbers shown, never silently with one.' },
  { id: 'index', name: 'Index', cost: 'CPU only',
    what: 'Precompute the answers to the known question types, with their marks.',
    how: ['Per-view counts and areas per room, unit and floor are stored with the marks that prove them.', 'Question wordings in every language map to the same stored query.', 'Text on the sheet is indexed for lookup questions.'],
    out: 'A lookup table. Most questions later cost one small parsing call and no drawing work.', fail: 'A question outside the table falls back to a query on the drawing model, then to a refusal with the reason.' },
];

// Per file: stop = index of the last stage it goes through; t = trace lines per stage.
const FILES = [
  { path: 'plans/floor-01.dxf', size: '388 kB', kind: 'DXF', route: 'vector', stop: 7, speed: 2, cost: 0, res: ['ok', 'ready'],
    t: [['path stays inside the target folder', '388 kB, under the 200 MB cap', 'sha256 4be1c09a… not seen before'],
      ['first bytes: AutoCAD DXF, version AC1027', 'same name as floor-01.pdf: one drawing, two renderings'],
      ['vector route: DXF is the source', 'floor-01.pdf kept to show evidence on'],
      ['units: metres, from the file header', 'upright, 1 view (floor plan)', 'scale exact: coordinates are real-world'],
      ['layers read: WALL, DOOR, WINDOW, FIXTURE, ROOM_TEXT', '13 rooms closed from wall loops', '12 door openings, 11 windows, 8 fixtures'],
      ['13 rooms, 23 openings, 8 fixtures, 2 units written', 'all elements carry a source region'],
      ['second count on the PDF rendering: 9 of 9 quantities agree'], ['9 quantities stored with marks']] },
  { path: 'plans/floor-01.pdf', size: '96 kB', kind: 'PDF, vector', route: 'copy', stop: 2, speed: 1, cost: 0, res: ['mute', 'display copy'],
    t: [['path ok, 96 kB', 'sha256 77a0d3e2… not seen before'], ['first bytes: PDF 1.7, 1 page, vector content', 'same drawing as plans/floor-01.dxf'], ['not parsed: the DXF carries more structure', 'kept as the rendering evidence is shown on']] },
  { path: 'plans/floor-02.dxf', size: '402 kB', kind: 'DXF', route: 'vector', stop: 7, speed: 2, cost: 0, res: ['ok', 'ready'], plan: 'A',
    t: [['path stays inside the target folder', '402 kB, under the 200 MB cap', 'sha256 c21f88b0… not seen before'],
      ['first bytes: AutoCAD DXF, version AC1027', 'same name as floor-02.pdf and floor-02.png: one drawing, three renderings'],
      ['vector route: DXF is the source', 'floor-02.pdf kept to show evidence on, floor-02.png for the second count'],
      ['units: metres, from the file header', 'upright, 1 view (floor plan)', 'scale exact: coordinates are real-world'],
      ['layers read: WALL, DOOR, WINDOW, FIXTURE, ROOM_TEXT, UNIT_OUTLINE', '15 indoor rooms and 2 balconies closed from wall loops', '16 door openings: 14 with a leaf (1 double), 2 open doorways', '13 windows, 8 fixtures'],
      ['17 rooms, 29 openings, 8 fixtures, 2 units written', 'rule recorded: open doorways are not doors'],
      ['second count on the PNG: 10 of 10 quantities agree', 'room areas sum to the unit outlines within 0.1%'], ['10 quantities stored with marks']] },
  { path: 'plans/floor-02.pdf', size: '101 kB', kind: 'PDF, vector', route: 'copy', stop: 2, speed: 1, cost: 0, res: ['mute', 'display copy'],
    t: [['path ok, 101 kB', 'sha256 0d9e41c7… not seen before'], ['first bytes: PDF 1.7, 1 page, vector content', 'same drawing as plans/floor-02.dxf'], ['not parsed', 'kept as the rendering evidence is shown on']] },
  { path: 'plans/floor-02.png', size: '1.2 MB', kind: 'PNG 2480×1754', route: 'copy', stop: 2, speed: 1, cost: 0, res: ['mute', 'check copy'],
    t: [['path ok, 1.2 MB', 'sha256 a6b2f5d1… not seen before'], ['first bytes: PNG, 2480×1754', 'same drawing as plans/floor-02.dxf'], ['not parsed', 'kept as the image the second count runs on']] },
  { path: 'plans/floor-03.dwg', size: '517 kB', kind: 'DWG', route: 'vector', stop: 7, speed: 2, cost: 0, res: ['ok', 'ready'],
    t: [['path stays inside the target folder', '517 kB', 'sha256 e90c2a44… not seen before'],
      ['first bytes: AutoCAD DWG, version AC1032', 'no other rendering with this name'],
      ['vector route', 'DWG converted to DXF once, the conversion is cached by hash', 'no rendering in the archive: one is drawn from the DXF to show evidence on'],
      ['units: millimetres, from the file header, converted to metres', 'upright, 1 view (floor plan)'],
      ['layers read: A-WALL, A-DOOR, A-GLAZ, P-FIXT, A-AREA-IDEN', 'layer names differ from floor-01 and -02: mapped by the layer dictionary', '14 rooms, 12 doors, 12 windows, 8 fixtures'],
      ['14 rooms, 24 openings, 8 fixtures, 2 units written'],
      ['second count on the drawn rendering: 10 of 10 quantities agree'], ['10 quantities stored with marks']] },
  { path: 'model/harbour-block.ifc', size: '18.4 MB', kind: 'IFC4', route: 'model', stop: 7, speed: 3, cost: 0, res: ['ok', 'ready, 4 levels'],
    t: [['path stays inside the target folder', '18.4 MB', 'sha256 5f7703be… not seen before'],
      ['first bytes: ISO-10303-21, schema IFC4', '4 building storeys found'],
      ['model route: quantities are read from the model, no image work', 'a plan is rendered per storey to show evidence on'],
      ['units: metres (IfcUnitAssignment)', '4 views, one per storey'],
      ['62 IfcSpace, 58 IfcDoor, 71 IfcWindow, 212 IfcWall', 'areas and volumes from the quantity sets; 3 spaces without one are computed from geometry'],
      ['4 views written, elements linked to their storey', '3 computed areas marked "from geometry"'],
      ['storeys 2 and 3 match floor-02.dxf and floor-03.dwg on doors and windows', 'storey 1: the model has 1 more door than floor-01.dxf, flagged for review'], ['41 quantities stored with marks', 'volumes available for this source only']] },
  { path: 'sheets/A-201-plan-sections.pdf', size: '2.9 MB', kind: 'PDF, scan inside', route: 'raster', stop: 7, speed: 4, cost: 0.0034, res: ['ok', 'ready, 3 views'],
    t: [['path stays inside the target folder', '2.9 MB', 'sha256 1c84e6fa… not seen before'],
      ['first bytes: PDF 1.4, 1 page', 'the page is a single embedded image: a scan in a PDF wrapper'],
      ['raster route, page rendered at 300 dpi'],
      ['upright, skew 0.4° corrected', '3 views on the sheet: 1 floor plan, 2 sections', 'written scale "1:100" found in the title block'],
      ['plan view: 9 rooms, 10 doors, 9 windows, 6 fixtures', 'sections: storey heights read from level marks, no counts'],
      ['3 views written, each with its own region of the sheet'],
      ['second count on the plan view: 8 of 8 quantities agree'], ['8 quantities stored for the plan view', 'count questions on the section views are refused with the reason']] },
  { path: 'scans/flat-b12-scan.png', size: '840 kB', kind: 'PNG 1240×1754', route: 'raster', stop: 7, speed: 4, cost: 0.0031, res: ['warn', '2 to review'], plan: 'B',
    t: [['path stays inside the target folder', '840 kB', 'sha256 b3d9a172… not seen before'],
      ['first bytes: PNG, 1240×1754, 8-bit grey', 'no other rendering with this name'],
      ['raster route'],
      ['text reads upside down: rotated 180°', 'skew 0.9° corrected', '1 view (floor plan)', 'no written scale; scale bar 0 to 5 m found, 1:100 ±1.5%'],
      ['detector: 7 doors, 1 open doorway, 6 windows, 4 fixtures', 'OCR room labels: OH, K, ET, MH, MH, KH, S, PARVEKE', '7 indoor rooms and 1 balcony from wall segmentation'],
      ['8 rooms, 15 openings, 4 fixtures, 1 unit written', 'highlighter stroke over room OH ignored'],
      ['second count: 7 of 8 quantities agree', 'windows: detector 6, vision 7. The difference is the balcony glazing: contested', 'area: scale uncertainty 1.5% is close to the 2% tolerance: flagged'], ['8 quantities stored with marks', '2 in the review queue']] },
  { path: 'scans/flat-c03-photo.jpg', size: '38 kB', kind: 'JPEG 320×240', route: 'raster', stop: 7, speed: 4, cost: 0.0019, res: ['warn', 'low resolution'],
    t: [['path stays inside the target folder', '38 kB', 'sha256 d47a90c3… not seen before'],
      ['first bytes: JPEG, 320×240', 'phone photo of a paper plan'],
      ['raster route'],
      ['rotated 90°', 'perspective corrected from the sheet edges', 'no scale found: lengths and areas will be refused'],
      ['walls and 4 room labels readable', 'door and window symbols are under 6 px: not reliable'],
      ['4 rooms written', 'openings and fixtures marked unavailable, not zero'],
      ['second count agrees on rooms only'], ['2 quantities stored (rooms, bedrooms)', 'other questions on this file answer "cannot be read at this resolution"']] },
  { path: 'specs/window-schedule.pdf', size: '214 kB', kind: 'PDF, encrypted', route: 'text', stop: 7, speed: 2, cost: 0, res: ['info', 'text only'],
    t: [['path stays inside the target folder', '214 kB', 'sha256 8e02b7d5… not seen before'],
      ['first bytes: PDF 1.6, AES-encrypted', 'opened with an empty password, 2 pages'],
      ['text route: the pages are tables, not drawings'],
      ['upright, no views to split'],
      ['1 table: 14 window types with size and glazing'],
      ['schedule rows written, keyed by window type code'],
      ['type codes W1 to W6 also appear on floor-02: linked'], ['indexed for lookup questions', 'no quantities']] },
  { path: 'archive/elevation-1962.jpg', size: '3.1 MB', kind: 'JPEG 2400×1700', route: 'raster', stop: 7, speed: 4, cost: 0.0022, res: ['info', 'no plan view'],
    t: [['path stays inside the target folder', '3.1 MB', 'sha256 39c5e1ab… not seen before'],
      ['first bytes: JPEG, 2400×1700', 'scan of a hand-drawn sheet'],
      ['raster route'],
      ['upright', '1 view: elevation', 'scale bar found, in metres'],
      ['title block read by OCR: street elevation, 1962', 'no floor plan on the sheet'],
      ['1 elevation view written, with its title block text'],
      ['nothing to count twice'], ['indexed for text lookup', 'room, door and area questions are refused: "this sheet has no floor plan"']] },
  { path: 'misc/site-photo-0412.jpg', size: '4.6 MB', kind: 'JPEG photo', route: 'skip', stop: 1, speed: 1, cost: 0, res: ['mute', 'set aside'],
    t: [['path ok, 4.6 MB', 'sha256 f1107c9e… not seen before'], ['first bytes: JPEG with camera EXIF', 'classified as a photograph, not a drawing: set aside']] },
  { path: 'misc/Thumbs.db', size: '22 kB', kind: 'system file', route: 'skip', stop: 1, speed: 1, cost: 0, res: ['mute', 'ignored'],
    t: [['path ok, 22 kB'], ['Windows thumbnail cache: ignored']] },
];
// Conflicts the ingest found between two readings of the same thing. ai = index of the variant the rules picked,
// null when the rules could not decide. verdict/pick are what the user did.
const CONFLICTS = [
  { id: 'c1', file: 'model/harbour-block.ifc ↔ plans/floor-01.dxf', title: 'Doors on storey 1', ai: 0,
    v: [{ label: '13 doors', src: 'IFC model, IfcDoor on storey 1' }, { label: '12 doors', src: 'DXF, DOOR layer of floor-01' }],
    rules: ['A BIM model outranks CAD when both carry the same revision.', 'Both files carry revision C, dated 2026-09-14.'],
    why: 'Same revision, so the model wins. The extra door (D-1.14, storage) is drawn in the model and missing from the DXF.' },
  { id: 'c2', file: 'plans/floor-03.dwg', title: 'Glazed door on layer A-GLAZ', ai: 1,
    v: [{ label: 'Window', src: 'Layer A-GLAZ, where windows live' }, { label: 'Door', src: 'Block has a door leaf and a swing arc' }],
    rules: ['Glazed doors count as doors.', 'An opening with a leaf and a swing is a door, whatever its layer.'],
    why: 'The block has a leaf and a swing arc, so it is a door. The layer name is overruled.' },
  { id: 'c3', file: 'sheets/A-201-plan-sections.pdf', title: 'Scale of the plan view', ai: 0,
    v: [{ label: '1:100', src: 'Written scale in the title block' }, { label: '1:98', src: 'Measured from the drawn scale bar' }],
    rules: ['Scale, in order of trust: CAD units, a written scale, a drawn scale bar, dimension strings.'],
    why: 'A written scale is trusted over a scale bar. The 2% gap is within what a scan stretches.' },
  { id: 'c4', file: 'specs/window-schedule.pdf ↔ plans/floor-02', title: 'Size of window type W4', ai: 0,
    v: [{ label: '1200 × 1400', src: 'Window schedule, row W4' }, { label: '1200 × 1500', src: 'Tag next to the window on floor-02' }],
    rules: ['A schedule outranks a tag on the plan.', 'The newer document wins when the dates differ.'],
    why: 'Both are dated 2026-08-02, so the schedule wins.' },
  { id: 'c5', file: 'scans/flat-b12-scan.png', title: 'Windows: is the balcony glazing a window?', ai: null,
    v: [{ label: '6 windows', src: 'Detector: glazing is not a window in a wall' }, { label: '7 windows', src: 'Vision count: glazing counted as a window' }],
    rules: ['One window per opening in a wall, whatever the number of panes.', 'Balcony glazing on an outdoor railing is not a wall.'],
    why: 'The scan does not show whether the glazing sits in a wall or on the railing. Both readings follow the rules.',
    apply: (i) => { PLANS.B.q.windows.marks.find((m) => m.id === 'w7').state = i === null ? 'contested' : i === 0 ? 'rejected' : 'counted'; } },
  { id: 'c6', file: 'scans/flat-c03-photo.jpg', title: 'Label of the second room', ai: null,
    v: [{ label: 'MH (bedroom)', src: 'OCR, 54% confidence' }, { label: 'KH (bathroom)', src: 'OCR second reading, 41% confidence' }],
    rules: ['A room label is only used when OCR is over 80% sure.', 'A room without a label is never guessed.'],
    why: 'Both readings are under 80%. The photo is 320×240, too small to settle it.' },
];
const finalPick = (c) => (c.verdict === 'approved' ? c.ai : c.pick ?? null);
const resolved = (c) => finalPick(c) !== null;
const cfList = (mode) => CONFLICTS.filter((c) => (mode === 'solved') === (c.ai !== null));

FILES.forEach((f, i) => { f.start = i * 2; f.end = f.start + (f.stop + 1) * f.speed; });
const MAX_T = Math.max(...FILES.map((f) => f.end));
const ROUTE_CHIP = { vector: ['info', 'vector'], model: ['info', 'model'], raster: ['warn', 'raster'], text: ['mute', 'text'], copy: ['mute', 'copy'], skip: ['mute', 'none'] };

// which stage a file is in at time t: -1 not started, 0..stop running, stop+1 finished
function at(f, t) {
  if (t < f.start) return -1;
  return Math.min(f.stop + 1, Math.floor((t - f.start) / f.speed));
}

/* ------------------------------------------------------------------ state */

const state = {
  view: 'ingest', role: 'engineer', plan: 'A', focus: 'doors', addMode: false,
  thread: [],
  ing: { t: -1, timer: null, zip: null },
};

/* ------------------------------------------------------------ plan → SVG */

function leaf(wall, x, y, g, swing, hinge) {
  // quarter-circle door leaf hinged at one end of a gap of width g centred on (x, y)
  const X = x * S, Y = y * S, G = g * S;
  if (wall === 'v') {
    const hy = Y - hinge * G / 2;
    return `M${X} ${hy} L${X + swing * G} ${hy} A${G} ${G} 0 0 ${swing * hinge > 0 ? 1 : 0} ${X} ${Y + hinge * G / 2}`;
  }
  const hx = X - hinge * G / 2;
  return `M${hx} ${Y} L${hx} ${Y + swing * G} A${G} ${G} 0 0 ${swing * hinge > 0 ? 0 : 1} ${X + hinge * G / 2} ${Y}`;
}
function gap(wall, x, y, len) {
  const X = x * S, Y = y * S, L = len * S / 2;
  return wall === 'v' ? `<line class="pl-gap" x1="${X}" y1="${Y - L}" x2="${X}" y2="${Y + L}"/>` : `<line class="pl-gap" x1="${X - L}" y1="${Y}" x2="${X + L}" y2="${Y}"/>`;
}
function doorSVG(d) {
  const g = d.double ? 1.5 : d.small ? 0.7 : 0.9;
  let s = gap(d.wall, d.x, d.y, g);
  if (d.open) return s;
  if (d.double) {
    const off = g / 4;
    const a = d.wall === 'v' ? [d.x, d.y - off, d.x, d.y + off] : [d.x - off, d.y, d.x + off, d.y];
    s += `<path class="pl-sym" d="${leaf(d.wall, a[0], a[1], g / 2, d.swing, 1)}"/><path class="pl-sym" d="${leaf(d.wall, a[2], a[3], g / 2, d.swing, -1)}"/>`;
  } else s += `<path class="pl-sym" d="${leaf(d.wall, d.x, d.y, g, d.swing, d.hinge)}"/>`;
  return s;
}
function windowSVG(w) {
  const len = w.len || 1.4, X = w.x * S, Y = w.y * S, L = len * S / 2;
  const r = w.wall === 'v' ? [X - 5, Y - L, 10, 2 * L] : [X - L, Y - 5, 2 * L, 10];
  const c = w.wall === 'v' ? [X, Y - L, X, Y + L] : [X - L, Y, X + L, Y];
  return gap(w.wall, w.x, w.y, len) + `<rect class="pl-sym thin" x="${r[0]}" y="${r[1]}" width="${r[2]}" height="${r[3]}"/><line class="pl-sym thin" x1="${c[0]}" y1="${c[1]}" x2="${c[2]}" y2="${c[3]}"/>`;
}
const FIX = {
  wc: '<rect class="pl-fix" x="-10" y="-22" width="20" height="10"/><ellipse class="pl-fix" cx="0" cy="1" rx="9" ry="12"/>',
  basin: '<rect class="pl-fix" x="-13" y="-10" width="26" height="20" rx="5"/><circle class="pl-fix" cx="0" cy="0" r="2.5"/>',
  bath: '<rect class="pl-fix" x="-18" y="-42" width="36" height="84"/><rect class="pl-fix" x="-13" y="-36" width="26" height="72" rx="11"/>',
  shower: '<rect class="pl-fix" x="-20" y="-20" width="40" height="40"/><path class="pl-fix" d="M-20 -20L20 20M20 -20L-20 20"/>',
  sink: '<rect class="pl-fix" x="-27" y="-13" width="54" height="26"/><rect class="pl-fix" x="-22" y="-9" width="19" height="18"/><rect class="pl-fix" x="3" y="-9" width="19" height="18"/>',
};

function planSVG(p, q, survey) {
  const m = 0.9;
  const vb = [(p.minX - m) * S, (p.minY - m) * S, (p.W + 2 * m) * S, (p.H + 2 * m + 0.5) * S];
  const rect = (r, cls, extra = '') => `<rect class="${cls}" x="${r.x * S}" y="${r.y * S}" width="${r.w * S}" height="${r.h * S}" ${extra}/>`;
  let s = `<svg viewBox="${vb.join(' ')}" class="${survey ? 'survey' : ''}" role="img" aria-label="${esc(p.title)}">
<defs><pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#ecebe6"/><line x1="0" y1="0" x2="0" y2="10" stroke="#9aa0ab" stroke-width="2"/></pattern></defs>`;
  if (p.scan) s += `<rect x="${vb[0]}" y="${vb[1]}" width="${vb[2]}" height="${vb[3]}" fill="#f7f1df"/><g class="scan" transform="rotate(-0.9 ${p.W * S / 2} ${p.H * S / 2})">`;
  s += p.rooms.map((r) => rect(r, 'pl-room' + (r.kind === 'out' ? ' out' : ''))).join('');
  if (p.scan) s += `<path d="M40 150 C 90 120, 150 170, 215 140" stroke="#f0df4a" stroke-width="26" stroke-linecap="round" fill="none" opacity="0.55"/>`;
  if (q && q.kind === 'area') {
    s += q.parts.map((pt) => { const r = p.rooms.find((x) => x.id === pt.id); return rect(r, 'shade ' + (pt.inc ? 'inc' : 'exc'), `data-part="${pt.id}"`); }).join('');
  }
  s += p.rooms.map((r) => rect(r, 'pl-wall' + (r.kind === 'out' ? ' out' : ''))).join('');
  s += p.doors.map(doorSVG).join('') + p.windows.map(windowSVG).join('');
  s += p.fixtures.map((f) => `<g transform="translate(${f.x * S} ${f.y * S}) rotate(${f.rot || 0})">${FIX[f.type]}</g>`).join('');
  s += p.rooms.map((r) => {
    const c0 = center(r), c = { x: r.lx || c0.x, y: r.ly || c0.y }, small = r.w < 2.6 || r.h < 2.2, pt = q && q.kind === 'area' && q.parts.find((x) => x.id === r.id);
    const up = r.w < 1.6 ? ` transform="rotate(-90 ${c.x * S} ${c.y * S})"` : '';
    return `<g${up}><text class="pl-label${small ? ' s' : ''}" x="${c.x * S}" y="${c.y * S - (small ? 2 : 4)}">${esc(r.name)}</text>` +
      (pt ? `<text class="shade-t${pt.inc ? '' : ' exc'}" x="${c.x * S}" y="${c.y * S + 15}">${pt.inc ? '' : 'not in sum · '}${pt.area.toFixed(2)}</text>`
        : `<text class="pl-id" x="${c.x * S}" y="${c.y * S + 13}">${r.id}</text>`) + '</g>';
  }).join('');
  const by = (p.H + 0.75) * S, bx = p.minX * S;
  s += `<path class="pl-sym thin" d="M${bx} ${by}h${5 * S}M${bx} ${by - 5}v10M${bx + S} ${by - 3}v6M${bx + 2 * S} ${by - 3}v6M${bx + 3 * S} ${by - 3}v6M${bx + 4 * S} ${by - 3}v6M${bx + 5 * S} ${by - 5}v10"/><text class="pl-scale" x="${bx}" y="${by + 20}">0</text><text class="pl-scale" x="${bx + 5 * S - 8}" y="${by + 20}">5 m</text>`;
  if (q && q.kind === 'count') {
    let n = 0;
    s += q.marks.map((mk) => {
      const t = mk.state === 'counted' || mk.state === 'added' ? ++n : mk.state === 'contested' ? '?' : mk.state === 'rejected' ? '×' : '–';
      return `<g class="mark ${mk.state}" data-mark="${mk.id}" transform="translate(${mk.x * S} ${mk.y * S})"><circle r="15"/><text>${t}</text></g>`;
    }).join('');
  }
  if (p.scan) s += '</g>';
  return s + '</svg>';
}

function viewerHTML(p, q, survey) {
  const legend = q && q.kind === 'area'
    ? '<span><i style="background:#24588f;opacity:.45;border-radius:2px"></i>in the sum</span><span><i style="background:#c9c8c2;border-radius:2px"></i>left out by the rule</span>'
    : '<span><i style="background:#c8402a"></i>counted</span><span><i style="border:1px dashed #8a909c"></i>left out by the rule</span><span><i style="background:#e0a21b"></i>methods disagree</span>' +
      (survey ? '<span><i style="border:1px solid #c8402a"></i>rejected by you</span>' : '');
  return `<section class="card viewer${state.addMode ? ' adding' : ''}" id="viewer">
    <div class="cap"><span class="nm">${esc(p.file)}</span><span class="chip ${ROUTE_CHIP[p.route][0]}">${p.route} route</span><span>${esc(p.caption)}</span></div>
    <div class="stagebox">${planSVG(p, q, survey)}</div>
    <div class="legend">${legend}<span style="margin-left:auto">${q ? esc(q.label) : ''}</span></div>
  </section>`;
}

/* -------------------------------------------------------------- workspace */

function sideHTML() {
  const rows = [
    ['A', 'plans/floor-02', 'DXF · vector route', PLANS.A],
    ['B', 'scans/flat-b12-scan', 'PNG scan · raster route', PLANS.B],
    [null, 'plans/floor-01', 'DXF'], [null, 'plans/floor-03', 'DWG'], [null, 'model/harbour-block', 'IFC, 4 levels'],
    [null, 'sheets/A-201', 'scan, 3 views'], [null, 'scans/flat-c03-photo', 'low resolution'],
  ];
  return `<aside class="card side"><h2>Drawings <small>7 of 9 documents</small></h2><ul class="dlist">${rows.map(([id, nm, meta, p]) => {
    const rev = p ? Object.values(p.q).filter((q) => status(q)[0] === 'warn').length : 0;
    return `<li><button ${id ? `data-plan="${id}"` : 'disabled title="Not drawn in this mock"'} class="${id === state.plan ? 'on' : ''}"><span class="nm">${nm}</span><span class="meta">${meta}${rev ? ` · ${rev} to review` : ''}${id ? '' : ' · not in this mock'}</span></button></li>`;
  }).join('')}</ul></aside>`;
}

function evidenceHTML(q, survey) {
  if (q.kind === 'count') {
    let n = 0;
    return `<ol class="ev">${q.marks.map((m) => {
      const no = m.state === 'counted' || m.state === 'added' ? ++n : m.state === 'contested' ? '?' : m.state === 'rejected' ? '×' : '–';
      const note = m.state === 'rejected' ? 'rejected by you' : m.state === 'added' ? 'added by you' : m.state === 'counted' && m.orig !== 'counted' ? 'counted by you' : m.note;
      const acts = !survey ? '' : m.state === 'contested'
        ? `<span class="acts"><button class="btn small ok" data-set="${m.id}:counted">Count it</button><button class="btn small no" data-set="${m.id}:rejected">Leave out</button></span>`
        : `<span class="acts"><button class="btn small" data-toggle="${m.id}">${m.state === 'added' ? 'Remove' : m.state === 'counted' ? 'Reject' : 'Count'}</button></span>`;
      return `<li class="${m.state}" data-hot="${m.id}"><span class="no">${no}</span><span class="t">${esc(m.name)}${note ? `<small>${esc(note)}</small>` : ''}</span>${acts}</li>`;
    }).join('')}</ol>`;
  }
  const inc = q.parts.filter((p) => p.inc);
  return `<ol class="ev">${q.parts.map((p) => `<li class="${p.inc ? 'inc' : 'exc'}" data-hot="${p.id}"><span class="no">${p.inc ? '+' : '–'}</span><span class="t">${esc(p.id)} ${esc(p.name)}${!p.inc ? `<small>${esc(p.why || 'left out by you')}</small>` : p.orig ? '' : '<small>added by you</small>'}</span><span class="r">${p.area.toFixed(2)}</span>${survey ? `<span class="acts"><button class="btn small" data-part-toggle="${p.id}">${p.inc ? 'Leave out' : 'Include'}</button></span>` : ''}</li>`).join('')}</ol>
  <p class="sum">${inc.map((p) => p.area.toFixed(2)).join(' + ') || '0'} = <b>${value(q).toFixed(2)} m²</b></p>`;
}

// Where an answer's facts came from, per drawing (mock file names, same as the ingest list).
const SOURCES = {
  A: [['plans/floor-02.dxf', 'CAD', 'Read: rooms, doors, windows and fixtures from the CAD layers'],
    ['plans/floor-02.pdf', 'PDF', 'Shown: the rendering the marks are drawn on'],
    ['plans/floor-02.png', 'PNG', 'Checked: a second, independent count by a small vision model']],
  B: [['scans/flat-b12-scan.png', 'SCAN', 'Read: symbol detector and OCR on the scanned sheet'],
    ['scans/flat-b12-scan.png', 'SCAN', 'Checked: a second, independent count by a small vision model']],
};

// Confidence = how much independent information backs the number (mock rule, shown to the user).
function confidence(p, q) {
  if (q.signed) return [99, 'high', 'Signed off by a surveyor.'];
  if (contested(q)) return [55, 'low', `The two methods disagree (${fmt(q)} or ${q.altValue}). A surveyor has to settle it.`];
  if (q.flag) return [76, 'medium', q.flag];
  if (p.route === 'vector') return [97, 'high', 'Exact CAD geometry, and the second count agrees.'];
  return [88, 'medium', 'Read from a scan, but the second count agrees.'];
}

function suggestHTML(p) {
  const asked = new Set(state.thread.map((e) => e.text));
  const left = SUGGEST[p.id].filter((t) => !asked.has(t));
  return left.length ? `<div class="try">${left.map((t) => `<button data-ask="${esc(t)}">${esc(t)}</button>`).join('')}</div>` : '';
}

function answerHTML(e, i) {
  const p = PLANS[e.plan], last = i === state.thread.length - 1;
  const user = `<div class="u-row"><div class="bubble">${esc(e.text)}</div><span class="avatar">YOU</span></div>`;
  const bot = (inner) => `<div class="a-row"><span class="bot" aria-hidden="true"></span><div class="a-body">${inner}</div></div>`;
  if (e.pending) return `<article class="turn">${user}${bot(`<div class="steps-done"><span class="spin"></span> Reading ${esc(p.file)}…</div>`)}</article>`;
  if (!e.key) {
    return `<article class="turn">${user}${bot(`<p><b>I can't answer that from this drawing.</b> ${esc(e.reason)}</p><p class="mute">No answer is better than a guess, so the confidence is 0%.</p>
      ${last ? suggestHTML(p) : ''}`)}</article>`;
  }
  const q = p.q[e.key], [pct, lvl, why] = confidence(p, q);
  const card = `<div class="rcard${e.hidden ? ' closed' : ''}">
    <div class="rhead"><span class="ricon">⌗</span><b>${esc(q.label)}</b><span class="rsub">${esc(p.file)} · ${p.route === 'vector' ? 'CAD' : 'scan'}</span>
      <button class="hide" data-hide="${i}">${e.hidden ? 'Show ⌄' : 'Hide ⌃'}</button></div>
    <div class="rbody">
      <div class="shot">${planSVG(p, q, false)}</div>
      <div class="rside">
        <span class="k">The answer</span>
        <dl><dt>Value</dt><dd><b>${fmt(q)}</b> ${esc(q.unit)}</dd><dt>Rule</dt><dd>${esc(q.rule)}</dd><dt>Method</dt><dd>${esc(q.method)}</dd><dt>Check</dt><dd>${esc(q.alt)}: ${q.kind === 'count' ? q.altValue : 'agrees'}</dd></dl>
        <span class="k">Confidence</span>
        <div class="confrow"><div class="conf ${lvl}"><i style="width:${pct}%"></i></div><b>${pct}%</b></div>
        <small>${esc(why)}</small>
        <span class="k">Where this came from</span>
        <ul class="srcs">${SOURCES[p.id].map(([f, k, w]) => `<li><span class="tag">${k}</span><span><b>${esc(f)}</b><small>${esc(w)}</small></span></li>`).join('')}</ul>
      </div>
    </div>
    <div class="rfoot"><span class="fld"><small>Drawing</small> ${esc(p.file)}</span><span class="fld"><small>Cost</small> ${eur(e.cost)}</span><span class="fld"><small>Time</small> ~40 ms</span>
      <span style="flex:1"></span><button class="btn primary" data-survey="${e.key}">▸ Send to surveyor</button></div>
  </div>`;
  const text = q.kind === 'area' ? `The ${esc(q.label.toLowerCase())} is <b>${fmt(q)} m²</b>. ${esc(q.rule)}`
    : `There ${fmt(q) === '1' ? 'is' : 'are'} <b>${fmt(q)} ${esc(q.unit)}</b> on this drawing. ${esc(q.rule)}`;
  const note = lvl === 'high' ? '' : `<p>One thing before you use it: ${esc(why)}</p>`;
  return `<article class="turn">${user}${bot(`<p>${text}</p>${card}${note}${last ? suggestHTML(p) : ''}`)}</article>`;
}

function engineerHTML(p) {
  return `<section class="chat">
    ${state.thread.length ? '' : `<header class="hero"><h1>${esc(p.title)}</h1></header>${suggestHTML(p)}`}
    <div class="convo" id="convo">${state.thread.map(answerHTML).join('')}</div>
    <form class="composer" id="ask"><span class="plus">+</span><input name="q" placeholder="Ask a question about this drawing…" autocomplete="off">
      <span class="meta">${state.thread.length} asked</span><button aria-label="Ask">➤</button></form>
  </section>`;
}

function surveyorHTML(p) {
  const qs = Object.values(p.q), done = qs.filter((q) => q.signed).length, q = p.q[state.focus] || qs[0];
  const st = status(q), blocked = contested(q);
  return `<section class="card panel"><h2 style="padding:9px 12px;border-bottom:1px solid var(--line-soft);display:flex;justify-content:space-between;align-items:center">Takeoff: ${esc(p.file)} <button class="btn small" id="csv">Export CSV</button></h2>
    <div class="body" style="padding-bottom:6px"><span class="lbl">${done} of ${qs.length} quantities signed off</span><div class="progress"><i style="width:${100 * done / qs.length}%"></i></div></div>
    <div class="tablewrap"><table class="takeoff"><thead><tr><th>Quantity</th><th class="num">Value</th><th>State</th></tr></thead><tbody>
    ${qs.map((x) => { const s = status(x), ch = value(x) !== x.origValue; return `<tr class="click${x.key === q.key ? ' sel' : ''}" data-q="${x.key}"><td>${esc(x.label)}</td><td class="v">${ch ? `<s>${fmt(x, x.origValue)}</s>` : ''}${fmt(x)}${x.kind === 'area' ? ' m²' : ''}</td><td><span class="chip ${s[0]}">${s[1]}</span></td></tr>`; }).join('')}
    </tbody></table></div>
    <div class="qdetail">
      <h3>${esc(q.label)} <span class="chip ${st[0]}">${st[1]}</span></h3>
      <div class="cmp"><div><b>${fmt(q)}</b><span>${esc(q.method)}${edited(q) ? ', with your edits' : ''}</span></div><div><b>${q.kind === 'count' ? q.altValue : fmt(q, q.origValue)}</b><span>${esc(q.alt)}</span></div></div>
      ${q.flag ? `<p class="refuse">${esc(q.flag)}</p>` : ''}
      <p><span class="lbl">Counting rule</span><br>${esc(q.rule)}</p>
      <p><span class="lbl">${q.kind === 'count' ? 'Marks: click one here or on the drawing to change it' : 'Rooms: click one here or on the drawing to change it'}</span></p>
      ${evidenceHTML(q, true)}
      <div class="tools">
        ${q.kind === 'count' ? `<button class="btn${state.addMode ? ' primary' : ''}" id="add">${state.addMode ? 'Click the drawing to place it…' : 'Add a missed one'}</button>` : ''}
        ${q.signed ? '<button class="btn" id="unsign">Reopen</button>' : `<button class="btn primary" id="sign" ${blocked ? 'disabled' : ''}>Sign off ${fmt(q)}${q.kind === 'area' ? ' m²' : ''}</button>`}
        ${edited(q) && !q.signed ? '<button class="btn" id="reset">Undo my edits</button>' : ''}
      </div>
      ${blocked ? '<p style="font-size:12px;color:var(--warn)">Settle the amber mark before signing.</p>' : ''}
      ${q.signed ? `<p class="signed">Signed off by you at ${q.signed}. Engineers now see this value as verified.</p>` : ''}
    </div></section>`;
}

function renderWork() {
  const p = PLANS[state.plan], survey = state.role === 'surveyor';
  let q = p.q[state.focus];
  if (survey && !q) { state.focus = 'doors'; q = p.q.doors; }
  $('#app').innerHTML = survey ? `<div class="work">${sideHTML()}${viewerHTML(p, q, survey)}${surveyorHTML(p)}</div>`
    : `<div class="work chat-mode">${sideHTML()}${engineerHTML(p)}</div>`;
}

function ask(text) {
  text = text.trim();
  if (!text) return;
  const p = PLANS[state.plan];
  const hit = MATCH.find(([re]) => re.test(text));
  const e = { text, plan: p.id, key: null, cost: PARSE_COST, cached: false };
  if (!hit) e.reason = 'This mock recognises count and area questions (doors, windows, toilets, sinks, baths, bedrooms, saunas, apartments, floor area). The product would say which part of the question it could not map to the drawing model.';
  else if (hit[1] === null) e.reason = 'This is a lookup in text, not a quantity. No fire rating is written on this sheet, and no specification is linked to it. The answer would need the door schedule or the specification.';
  else if (!p.q[hit[1]]) e.reason = `The drawing model of ${p.file} has nothing of that kind (for example, a single flat has no "apartment A").`;
  else e.key = hit[1];
  e.cached = state.thread.some((x) => x.plan === e.plan && x.text.toLowerCase() === text.toLowerCase());
  if (e.cached) e.cost = 0;
  e.pending = true;
  state.thread.push(e);
  renderWork();
  $('#convo').lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'start' });
  setTimeout(() => { e.pending = false; if (state.view === 'work' && state.role === 'engineer') renderWork(); }, 900);
}

function now() { return new Date().toTimeString().slice(0, 5); }

function workClick(ev) {
  const p = PLANS[state.plan], survey = state.role === 'surveyor', q = p.q[state.focus];
  const t = (sel) => ev.target.closest(sel);
  let el;
  if ((el = t('[data-plan]'))) { state.plan = el.dataset.plan; state.focus = 'doors'; state.addMode = false; return renderWork(); }
  if ((el = t('[data-ask]'))) return ask(el.dataset.ask);
  if ((el = t('[data-hide]'))) { const e = state.thread[+el.dataset.hide]; e.hidden = !e.hidden; return renderWork(); }
  if ((el = t('[data-survey]'))) { openWork('surveyor'); state.focus = el.dataset.survey; return renderWork(); }
  if (!survey) return;
  if ((el = t('[data-q]'))) { state.focus = el.dataset.q; state.addMode = false; return renderWork(); }
  if (t('#csv')) return exportCSV(p);
  if (t('#add')) { state.addMode = !state.addMode; return renderWork(); }
  if (t('#sign')) { q.signed = now(); return renderWork(); }
  if (t('#unsign')) { q.signed = null; return renderWork(); }
  if (t('#reset')) {
    if (q.kind === 'count') { q.marks = q.marks.filter((m) => m.orig !== 'added'); q.marks.forEach((m) => { m.state = m.orig; }); } else q.parts.forEach((x) => { x.inc = x.orig; });
    return renderWork();
  }
  if (q.signed) return;
  if ((el = t('[data-set]'))) { const [id, s] = el.dataset.set.split(':'); q.marks.find((m) => m.id === id).state = s; return renderWork(); }
  const toggleMark = (id) => {
    const m = q.marks.find((x) => x.id === id);
    if (m.state === 'added') q.marks = q.marks.filter((x) => x !== m);
    else if (m.state === 'counted') m.state = m.orig === 'excluded' ? 'excluded' : 'rejected';
    else m.state = 'counted';
    renderWork();
  };
  if ((el = t('[data-toggle]'))) return toggleMark(el.dataset.toggle);
  if ((el = t('[data-part-toggle]')) || (q.kind === 'area' && (el = t('[data-part]')))) {
    const x = q.parts.find((y) => y.id === (el.dataset.partToggle || el.dataset.part)); x.inc = !x.inc; return renderWork();
  }
  if (q.kind === 'count' && (el = t('[data-mark]')) && !state.addMode) return toggleMark(el.dataset.mark);
  const svg = t('#viewer svg');
  if (svg && state.addMode && q.kind === 'count') {
    const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const c = pt.matrixTransform(svg.getScreenCTM().inverse());
    const n = q.marks.filter((m) => m.orig === 'added').length + 1;
    q.marks.push({ id: 'add' + Date.now(), x: c.x / S, y: c.y / S, name: `Added by you (${n})`, state: 'added', orig: 'added', note: '' });
    state.addMode = false; renderWork();
  }
}

function workHover(ev) {
  const el = ev.target.closest('[data-hot],[data-mark],[data-part]');
  document.querySelectorAll('.hot').forEach((x) => x.classList.remove('hot'));
  if (!el) return;
  const id = el.dataset.hot || el.dataset.mark || el.dataset.part;
  document.querySelectorAll(`[data-hot="${id}"],[data-mark="${id}"],[data-part="${id}"]`).forEach((x) => x.classList.add('hot'));
}

function exportCSV(p) {
  const rows = [['drawing', 'quantity', 'value', 'unit', 'value_at_ingest', 'method', 'state', 'signed_off_at']];
  for (const q of Object.values(p.q)) rows.push([p.file, q.label, fmt(q), q.kind === 'area' ? 'm2' : 'count', fmt(q, q.origValue), q.method, status(q)[1], q.signed || '']);
  const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = p.file.split('/').pop() + '-takeoff.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ----------------------------------------------------------------- ingest */

const HINTS = ['opening the zip safely', 'what each file really is', 'picking the best source per drawing',
  'upright sheets, views and scale', 'reading rooms, doors, windows, fixtures', 'one schema for every drawing',
  'a second, independent count', 'precomputing the answers'];
const RING_R = 32, RING_C = 2 * Math.PI * RING_R;

function renderIngest() {
  const g = state.ing;
  if (g.t < 0) {
    $('#app').innerHTML = `<div class="landing"><div class="drop" id="drop"><h1>Drop a project archive here (.zip)</h1>
      <div class="actions"><button class="btn primary" id="sample">Use the sample archive (14 files)</button><label class="btn">Choose a zip<input type="file" id="pick" accept=".zip" hidden></label></div></div></div>`;
    return;
  }
  const done = g.t >= MAX_T;
  $('#app').innerHTML = `<div class="run"><div class="run-head"><span class="eyebrow"><i class="live"></i> ${done ? 'Analysis done' : 'Analysing now'}</span>
    <h1>${esc(g.zip)}</h1><p>Reading every drawing once, so later questions are answered from the result, not from the files.</p></div>
    <div class="console" id="console"></div>
    ${g.note ? `<p class="run-note">${esc(g.note)}</p>` : ''}
    ${done ? conflictSummaryHTML() : '<div class="run-actions"><button class="btn" id="again">Stop</button><button class="btn" id="skip">Skip to the end</button></div>'}</div>`;
  updateIngest();
}

/* -------------------------------------------------------------- conflicts */

function conflictSummaryHTML() {
  const sol = cfList('solved'), uns = cfList('unsolved'), n = (l) => l.filter(resolved).length, all = CONFLICTS.every(resolved);
  const tile = (l, mode, title, sub, btn) => `<div class="cftile${n(l) === l.length ? ' ok' : ''}"><span class="lbl">${title}</span>
    <b>${n(l)} / ${l.length}</b><span>${sub}</span><button class="btn${n(l) === l.length ? '' : ' primary'}" data-cf="${mode}">${btn}</button></div>`;
  return `<div class="cfsum"><h2>${CONFLICTS.length} conflicts found <small>two readings of the same thing disagree</small></h2>
    <div class="cftiles">${tile(sol, 'solved', 'Solved by the AI', 'checked by you', 'Approve solved conflicts')}${tile(uns, 'unsolved', 'Unsolved', 'variant chosen by you', 'See unsolved conflicts')}</div>
    <p class="cfgate">${all ? 'Every conflict is settled. The workspace answers from your decisions.' : 'The workspace opens when every conflict is approved or settled by you.'}</p>
    <div class="run-actions"><button class="btn" id="again">New archive</button><button class="btn primary" id="open" ${all ? '' : 'disabled'}>Open the workspace</button></div></div>`;
}

function conflictHTML(c) {
  const fin = finalPick(c), denied = c.verdict === 'denied';
  const vars = c.v.map((x, i) => `<div class="cfvar${fin === i ? ' chosen' : ''}${c.ai === i ? ' ai' : ''}"><span class="lbl">Variant ${i + 1}${c.ai === i ? ' · AI decision' : ''}</span><b>${esc(x.label)}</b><span>${esc(x.src)}</span></div>`).join('');
  const pickBtns = c.v.map((x, i) => `<button class="btn" data-pick="${c.id}:${i}">Use variant ${i + 1}: ${esc(x.label)}</button>`).join('');
  let act;
  if (fin !== null) act = `<p class="signed">${c.verdict === 'approved' ? `Approved by you: variant ${c.ai + 1}.` : `You chose variant ${fin + 1}${denied ? ', over the AI decision' : ''}.`}</p><button class="btn small" data-reset="${c.id}">Change</button>`;
  else if (c.ai === null) act = `<p class="cfask">Choose the variant that is right:</p>${pickBtns}`;
  else if (denied) act = `<p class="cfask">You denied the AI decision. Pick the right variant yourself:</p>${pickBtns}<button class="btn small" data-reset="${c.id}">Cancel</button>`;
  else act = `<button class="btn ok" data-verdict="${c.id}:approved">Approve</button><button class="btn no" data-verdict="${c.id}:denied">Deny</button>`;
  return `<article class="card cf${fin !== null ? ' done' : ''}"><header><div><h3>${esc(c.title)}</h3><span class="nm">${esc(c.file)}</span></div>
    <span class="chip ${fin !== null ? 'ok' : c.ai === null ? 'warn' : 'info'}">${fin !== null ? 'settled' : c.ai === null ? 'needs you' : 'to approve'}</span></header>
    <div class="cfvars">${vars}</div>
    <div class="cfrules"><span class="lbl">Rules applied</span><ol>${c.rules.map((r) => `<li>${esc(r)}</li>`).join('')}</ol>
      <p><b>${c.ai === null ? 'AI could not decide.' : `AI decision: variant ${c.ai + 1}.`}</b> ${esc(c.why)}</p></div>
    <div class="cfact">${act}</div></article>`;
}

function renderConflicts() {
  const mode = state.cmode, list = cfList(mode), n = list.filter(resolved).length;
  $('#app').innerHTML = `<div class="run cfpage"><div class="run-head"><button class="btn small" id="cfback">← Back to the summary</button>
    <h1>${mode === 'solved' ? 'Conflicts the AI solved' : 'Unsolved conflicts'}</h1>
    <p>${mode === 'solved' ? 'Approve each decision, or deny it and pick the variant yourself.' : 'The rules could not pick a variant. Choose one for each conflict.'}</p>
    <span class="lbl">${n} of ${list.length} settled</span><div class="progress"><i style="width:${100 * n / list.length}%"></i></div></div>
    <div class="cflist">${list.map(conflictHTML).join('')}</div></div>`;
}

function conflictsClick(ev) {
  const t = (sel) => ev.target.closest(sel), get = (id) => CONFLICTS.find((c) => c.id === id);
  let el, c;
  if (t('#cfback')) { state.view = 'ingest'; return render(); }
  if ((el = t('[data-verdict]'))) { const [id, v] = el.dataset.verdict.split(':'); c = get(id); c.verdict = v; c.pick = null; }
  else if ((el = t('[data-pick]'))) { const [id, i] = el.dataset.pick.split(':'); c = get(id); c.pick = +i; }
  else if ((el = t('[data-reset]'))) { c = get(el.dataset.reset); c.verdict = null; c.pick = null; }
  else return;
  if (c.apply) c.apply(finalPick(c));
  renderConflicts();
  // last one settled: back to the summary, like the ingest hands over when it finishes
  if (resolved(c) && cfList(state.cmode).every(resolved)) setTimeout(() => { if (state.view === 'conflicts') { state.view = 'ingest'; render(); } }, 900);
}

function setHTML(node, html) { if (node.dataset.h !== html) { node.innerHTML = html; node.dataset.h = html; } }

function updateIngest() {
  const g = state.ing, t = g.t;
  if (t < 0 || !$('#console')) return renderIngest();
  const n = STAGES.length, frac = Math.min(1, t / MAX_T), idx = Math.min(n - 1, Math.floor(frac * n)), pct = Math.round(frac * 100);
  const fin = FILES.filter((f) => at(f, t) > f.stop), cost = fin.reduce((sum, f) => sum + f.cost, 0);
  const drawings = fin.filter((f) => f.stop === n - 1).length, total = FILES.filter((f) => f.stop === n - 1).length;
  const rows = STAGES.map((st, i) => {
    const cls = frac >= 1 || i < idx ? 'done' : i === idx ? 'active' : 'pending';
    const through = FILES.filter((f) => f.stop >= i), passed = through.filter((f) => at(f, t) > i).length;
    return `<div class="srow ${cls}"><div class="shead"><span class="sicon"></span><span class="slabel">${st.name}</span>${cls === 'active' ? `<span class="shint">${HINTS[i]}</span>` : ''}</div>
      ${cls === 'active' ? `<div class="sdetail"><div class="sbar"><span style="width:${Math.round(100 * passed / through.length)}%"></span></div><span>${passed} / ${through.length} files</span></div>` : ''}</div>`;
  }).join('');
  setHTML($('#console'), `<div class="ctop"><div><span class="eyebrow"><i class="live"></i> ${frac >= 1 ? 'Done' : `Working on step ${idx + 1} of ${n}`}</span>
      <h3>${frac >= 1 ? 'Ready' : STAGES[idx].name}</h3><p>${frac >= 1 ? '9 drawings indexed. Questions are answered from the result.' : HINTS[idx]}</p></div>
      <div class="ring"><svg viewBox="0 0 80 80"><circle class="rtrack" cx="40" cy="40" r="${RING_R}"/><circle class="rfill" cx="40" cy="40" r="${RING_R}" stroke-dasharray="${RING_C}" stroke-dashoffset="${RING_C * (1 - frac)}"/></svg><span>${pct}<small>%</small></span></div></div>
    <div class="cstats">
      <div><span>Elapsed</span><b>${Math.round(t * 0.26)}s</b></div>
      <div><span>Remaining</span><b>${frac >= 1 ? '–' : '~' + Math.max(1, Math.round((MAX_T - t) * 0.26)) + 's'}</b></div>
      <div><span>Files through</span><b>${fin.length} / ${FILES.length}</b></div>
      <div><span>Drawings ready</span><b>${drawings} / ${total}</b></div>
      <div><span>Inference cost</span><b>${eur(cost)}</b></div></div>
    <div class="ctimeline"><div class="thead"><span class="lbl">Pipeline</span><div class="ttrack"><i style="width:${pct}%"></i></div></div>${rows}</div>`);
}

function startIngest(name, note) {
  const g = state.ing;
  clearInterval(g.timer);
  g.zip = name; g.note = note || ''; g.t = 0;
  g.timer = setInterval(tick, 260);
  updateIngest();
}
function tick() {
  const g = state.ing;
  g.t++;
  if (g.t >= MAX_T) { clearInterval(g.timer); g.timer = null; }
  if (state.view === 'ingest') (g.t >= MAX_T ? renderIngest : updateIngest)();
}

function openWork(role, plan) {
  state.view = 'work'; state.role = role; if (plan) state.plan = plan;
  state.focus = PLANS[state.plan].id === 'B' && role === 'surveyor' ? 'windows' : 'doors';
  state.addMode = false;
  render();
}

function ingestClick(ev) {
  const g = state.ing, t = (sel) => ev.target.closest(sel);
  if (t('#sample')) return startIngest('harbour-block-archive.zip');
  if (t('#skip')) { clearInterval(g.timer); g.timer = null; g.t = MAX_T; return renderIngest(); }
  if (t('#again')) { clearInterval(g.timer); g.timer = null; g.t = -1; return updateIngest(); }
  if (t('#open')) return openWork('engineer');
  const cf = t('[data-cf]');
  if (cf) { state.view = 'conflicts'; state.cmode = cf.dataset.cf; return render(); }
}

/* ------------------------------------------------------------------- shell */

function render() {
  document.querySelectorAll('#roleSwitch button').forEach((b) => b.classList.toggle('on', b.dataset.role === state.role));
  $('#roleSwitch').hidden = state.view !== 'work';
  if (state.view === 'ingest') renderIngest(); else if (state.view === 'conflicts') renderConflicts(); else renderWork();
}

const app = $('#app');
app.addEventListener('click', (ev) => ({ ingest: ingestClick, conflicts: conflictsClick, work: workClick }[state.view](ev)));
app.addEventListener('mouseover', (ev) => { if (state.view === 'work') workHover(ev); });
app.addEventListener('submit', (ev) => { ev.preventDefault(); if (ev.target.id === 'ask') ask(ev.target.elements.q.value); });
app.addEventListener('change', (ev) => {
  if (ev.target.id === 'pick' && ev.target.files[0]) startIngest(ev.target.files[0].name, 'This mock does not read your file. It plays the sample archive under your file\'s name.');
});
app.addEventListener('dragover', (ev) => { if (ev.target.closest('#drop')) { ev.preventDefault(); $('#drop').classList.add('over'); } });
app.addEventListener('dragleave', (ev) => { if (ev.target.closest('#drop')) $('#drop').classList.remove('over'); });
app.addEventListener('drop', (ev) => {
  if (!ev.target.closest('#drop')) return;
  ev.preventDefault();
  const f = ev.dataTransfer.files[0];
  startIngest(f ? f.name : 'harbour-block-archive.zip', f ? 'This mock does not read your file. It plays the sample archive under your file\'s name.' : '');
});
$('#roleSwitch').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-role]'); if (!b) return;
  state.role = b.dataset.role; state.addMode = false;
  if (!PLANS[state.plan].q[state.focus]) state.focus = 'doors';
  render();
});

// deep links for screenshots and for sending someone to one screen: #work/surveyor/B, #ingest/done
(function boot() {
  const [v, a, b] = location.hash.slice(1).split('/');
  if (v === 'work') { state.view = 'work'; state.role = a === 'surveyor' ? 'surveyor' : 'engineer'; if (PLANS[b]) state.plan = b;
    if (state.role === 'engineer') { render(); return ask(SUGGEST[state.plan][0]); }
    if (state.plan === 'B') state.focus = 'windows'; }
  if (v === 'ingest' && a === 'done') { state.ing.zip = 'harbour-block-archive.zip'; state.ing.t = MAX_T; }
  render();
})();
