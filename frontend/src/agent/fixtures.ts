// One ChatTurn of each kind (decision 0013's example shape), for the unit tests and the screenshot page.
import type { ChatTurn, LawCheck, Proposal } from './agent';

export const DID = 'adeefbbcc17559fc';

const base = {
  chat_id: 'c3f9a1b2c4d5',
  turn: 1,
  model: 'rules',
  cost_usd: 0,
  latency_s: 0.3,
  answers: [],
};

export const answerTurn: ChatTurn = {
  ...base,
  kind: 'answer',
  text: 'Bagno 1.01 is 7.56 m² [1].',
  evidence: [
    {
      n: 1,
      id: 'ev_1',
      drawing_id: DID,
      name: 'Drawn plan 1',
      page: 1,
      box: [0.31, 0.22, 0.38, 0.29],
      label: 'Bagno 1.01',
      sure: true,
      level: {
        level: 'high',
        basis: 'certified',
        text: 'Read from the drawn room outline and its label.',
      },
    },
  ],
  edit: null,
  options: null,
  steps: [
    {
      n: 1,
      tool: 'list_drawings',
      label: 'Listed the drawings of the project',
      status: 'ok',
      ms: 12,
    },
    { n: 2, tool: 'ask_drawings', label: 'Asked the drawings: room area', status: 'ok', ms: 640 },
  ],
};

export const dontKnowTurn: ChatTurn = {
  ...base,
  kind: 'dont_know',
  text: 'This drawing does not say which walls carry load. Structural drawings, a building model with LoadBearing, or an engineer would settle it.',
  evidence: [],
  edit: null,
  options: null,
  steps: [
    { n: 1, tool: 'list_walls', label: 'Listed the walls of Drawn plan 1', status: 'ok', ms: 90 },
    { n: 2, tool: 'search_law', label: 'Searched the building code', status: 'error', ms: 30 },
  ],
};

/** A dont_know with the pipeline's suggested questions as options. */
export const dontKnowOptionsTurn: ChatTurn = {
  ...dontKnowTurn,
  text: 'The drawings do not say how high the ceilings are.',
  options: [
    { label: 'How many doors are there?', message: 'How many doors are there?' },
    { label: 'How big is Bagno 1.01?', message: 'How big is Bagno 1.01?' },
  ],
};

export const conflictTurn: ChatTurn = {
  ...base,
  kind: 'conflict',
  text: 'The drawings disagree: the plan counts 11 doors [1], the door schedule lists 12 [2].',
  evidence: [
    {
      n: 1,
      id: 'ev_1',
      drawing_id: DID,
      name: 'Drawn plan 1',
      page: 1,
      box: [0.1, 0.1, 0.9, 0.9],
      label: 'Doors',
      sure: false,
      level: { level: 'medium', basis: 'agree', text: 'Two readers agree; not certified.' },
    },
    {
      n: 2,
      id: 'ev_2',
      drawing_id: DID,
      name: 'Door schedule',
      page: 2,
      box: [0.05, 0.6, 0.5, 0.95],
      label: 'Schedule',
      sure: false,
      level: null,
    },
  ],
  edit: null,
  options: null,
  steps: [{ n: 1, tool: 'list_conflicts', label: 'Listed the conflicts', status: 'ok', ms: 20 }],
};

export const needsInputTurn: ChatTurn = {
  ...base,
  kind: 'needs_input',
  text: 'There are two bathrooms. Which one do you mean?',
  evidence: [],
  edit: null,
  options: [
    { label: 'Bagno 1.01', message: 'Remove the wall between Bagno 1.01 and the bedroom' },
    { label: 'Bagno 1.05', message: 'Remove the wall between Bagno 1.05 and the bedroom' },
  ],
  steps: [
    { n: 1, tool: 'list_walls', label: 'Listed the walls of Drawn plan 1', status: 'ok', ms: 80 },
  ],
};

export const proposal: Proposal = {
  proposal_id: 'p1',
  drawing_id: DID,
  page: 1,
  state: 'proposed',
  removed: [
    {
      id: 'W4',
      polygon: [
        [0.4, 0.2],
        [0.41, 0.2],
        [0.41, 0.3],
        [0.4, 0.3],
      ],
      label: 'Wall W4, 2.87 m, 0.12 m thick',
    },
  ],
  added: [],
  rooms: [
    {
      id: 'R1+R2',
      label: 'Bagno 1.01 + Stanza 1.02',
      polygon: [
        [0.3, 0.2],
        [0.52, 0.2],
        [0.52, 0.3],
        [0.3, 0.3],
      ],
      area_before_m2: 24.04,
      area_after_m2: 24.56,
      was: ['R1', 'R2'],
    },
  ],
  unknowns: ['Whether wall W4 is load-bearing: this drawing does not say.'],
  flags: [
    { code: 'wet_room', text: 'A wet room changes: its waterproofing is redone and inspected.' },
  ],
};

export const editTurn: ChatTurn = {
  ...base,
  kind: 'edit',
  text: 'Removing the wall between Bagno 1.01 and Stanza 1.02 makes one room of 24.56 m² (+0.52 m²) [1].',
  evidence: [answerTurn.evidence[0] as ChatTurn['evidence'][number]],
  edit: proposal,
  options: null,
  steps: [
    {
      n: 1,
      tool: 'get_plan_geometry',
      label: 'Read the rooms and walls of Drawn plan 1',
      status: 'ok',
      ms: 40,
    },
    {
      n: 2,
      tool: 'propose_remove_wall',
      label: 'Removed wall W4 between Bagno 1.01 and Stanza 1.02',
      status: 'ok',
      ms: 120,
    },
  ],
};

/** A new room drawn by the user (AC-18): one added room, a room that shrinks, new walls. */
export const roomTurn: ChatTurn = {
  ...base,
  kind: 'edit',
  text: 'A storage room of 3.40 m² fits there; Stanza 1.02 shrinks to 13.08 m².',
  evidence: [],
  edit: {
    proposal_id: 'p2',
    drawing_id: DID,
    page: 1,
    state: 'proposed',
    removed: [],
    added: [
      {
        id: 'N1',
        polygon: [
          [0.6, 0.4],
          [0.7, 0.4],
          [0.7, 0.402],
          [0.6, 0.402],
        ],
        label: 'New wall, 2.10 m, 0.10 m thick',
      },
    ],
    rooms: [
      {
        id: 'R9',
        label: 'Storage',
        polygon: [
          [0.6, 0.4],
          [0.7, 0.4],
          [0.7, 0.48],
          [0.6, 0.48],
        ],
        area_before_m2: 0,
        area_after_m2: 3.4,
        was: [],
      },
      {
        id: 'R2',
        label: 'Stanza 1.02',
        polygon: [
          [0.55, 0.3],
          [0.7, 0.3],
          [0.7, 0.4],
          [0.55, 0.4],
        ],
        area_before_m2: 16.48,
        area_after_m2: 13.08,
        was: ['R2'],
      },
    ],
    unknowns: [],
    flags: [],
  },
  options: null,
  steps: [
    { n: 1, tool: 'propose_room', label: 'Drew a storage room in your area', status: 'ok', ms: 60 },
  ],
};

export const turnsOfEachKind = [answerTurn, editTurn, dontKnowTurn, conflictTurn, needsInputTurn];

/** An extraction_v1 document with two rooms on page 1 (`GET /api/drawings/{id}/model`), one without a polygon. */
export const model = {
  schema: 'extraction_v1',
  rooms: [
    {
      id: 'R3',
      type: 'bathroom',
      label: 'Bagno 1.01',
      page: 1,
      polygon: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.3, 0.3],
        [0.1, 0.3],
      ],
      box: [0.1, 0.1, 0.3, 0.3],
    },
    { id: 'R4', type: 'bedroom', label: null, page: 1, polygon: null, box: [0.3, 0.1, 0.6, 0.3] },
  ],
};

const clause = (ref: string, quote: string | null = null, quote_en: string | null = null) => ({
  ref,
  url: `https://example.org/${encodeURIComponent(ref)}`,
  quote,
  quote_en,
});

const related = (id: string, ref: string, summary: string): LawCheck['related'][number] => ({
  id,
  law_id: 'ch-zh-ls-700-1',
  law_number: 'LS 700.1',
  law_title: 'Planungs- und Baugesetz',
  law_title_en: 'Planning and Building Act',
  ref,
  url: `https://example.org/${id}`,
  summary_en: summary,
  text: '…',
  keywords: [],
  language: 'de',
  limits: [],
  topics: ['rooms'],
  drawing_checkable: false,
  checked: '2026-11-14',
  status_note: null,
});

/** One finding of each change kind, an AI finding and five related clauses (one already a finding's clause). */
export const lawZh: LawCheck = {
  pack: 'ch-zh',
  pack_name: 'Canton of Zürich building act',
  fail_means: "It would not meet the Canton of Zürich's rule; other cantons set their own.",
  findings: [
    {
      ev: 'ev_9',
      rule_id: 'ch-zh-room-window',
      title: 'A habitable room has a window (canton of Zürich)',
      change: 'now_passes',
      subject: 'Bagno 1.01',
      before: { status: 'fail', value: 0 },
      after: { status: 'pass', value: 1, why: null },
      comparison_text: 'at least',
      limit: 1,
      unit: 'window',
      clause: clause('PBG § 302 Abs. 1'),
    },
    {
      ev: 'ev_2',
      rule_id: 'ch-zh-room-area',
      title: 'A bedroom or living room is at least 10 m2 (canton of Zürich)',
      change: 'newly_fails',
      subject: 'Stanza 1.02',
      before: { status: 'pass', value: 16.48 },
      after: { status: 'fail', value: 8.9, why: null },
      comparison_text: 'at least',
      limit: 10,
      unit: 'm2',
      clause: clause(
        'Planungs- und Baugesetz des Kantons Zürich (PBG, LS 700.1), § 303 Abs. 1',
        'Wohn- und Schlafräume müssen eine Bodenfläche von mindestens 10 m² aufweisen.',
        'Living rooms and bedrooms must have a floor area of at least 10 m².',
      ),
    },
    {
      ev: null,
      rule_id: 'ch-zh-room-height',
      title: 'A habitable room is at least 2.4 m high',
      change: 'newly_cannot_tell',
      subject: 'Storage',
      before: { status: 'pass', value: null },
      after: { status: 'cannot_tell', value: null, why: 'rooms of a kind we could not tell' },
      comparison_text: 'at least',
      limit: 2.4,
      unit: 'm',
      clause: clause('PBG § 304'),
    },
    {
      ev: null,
      rule_id: 'ch-zh-door-width',
      title: 'An entrance door is at least 0.8 m wide',
      change: 'still_fails',
      subject: 'door D1',
      before: { status: 'fail', value: 0.7 },
      after: { status: 'fail', value: 0.7, why: null },
      comparison_text: 'at least',
      limit: 0.8,
      unit: 'm',
      clause: clause('BBV I § 34'),
    },
  ],
  unchanged: 6,
  ai_findings: [
    {
      clause_id: 'ch-zh-ls-700-1-305-1',
      subject: 'Storage',
      value: 3.4,
      comparison: '>=',
      limit: 4,
      unit: 'm2',
      verdict: 'would_not_meet',
      ref: '§ 305 Abs. 1',
      law: 'PBG',
      url: 'https://example.org/305',
      quote: 'Abstellräume …',
      quote_en: 'Storage rooms …',
      basis: 'ai_reading',
    },
  ],
  related: [
    related('ch-zh-ls-700-1-303-1', '§ 303 Abs. 1', 'Room areas (already a finding)'),
    related('ch-zh-ls-700-1-305-1', '§ 305 Abs. 1', 'Storage (already an AI finding)'),
    related('ch-zh-ls-700-1-302-2', '§ 302 Abs. 2', 'Daylight of habitable rooms'),
    related('ch-zh-ls-700-1-306-1', '§ 306 Abs. 1', 'Kitchens'),
    related('ch-zh-ls-700-1-307-1', '§ 307 Abs. 1', 'Ventilation of wet rooms'),
    related('ch-zh-ls-700-1-308-1', '§ 308 Abs. 1', 'Stairs'),
  ],
  note: 'A pre-check of 2 rules from Canton of Zürich building act, not a permit check. Structure, fire safety, escape routes and services are not checked.',
};

/** The storage room of AC-18 on a ch-zh project: the law section with every kind, its ev mark among the sources. */
export const lawRoomTurn: ChatTurn = {
  ...roomTurn,
  text: "Stanza 1.02 would be 8.9 m²; Zürich's rule asks at least 10 m² for a bedroom or living room [1].",
  evidence: [
    {
      n: 1,
      id: 'ev_2',
      drawing_id: DID,
      name: 'Drawn plan 1',
      page: 1,
      box: [0.55, 0.3, 0.7, 0.4],
      label: 'Stanza 1.02',
      sure: true,
      level: null,
    },
  ],
  edit: { ...(roomTurn.edit as Proposal), law: lawZh },
};

/** The same with no country picked: `law` null (LC-14). */
export const noPackRoomTurn: ChatTurn = {
  ...roomTurn,
  edit: { ...(roomTurn.edit as Proposal), law: null },
};
