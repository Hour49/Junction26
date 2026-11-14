// One ChatTurn of each kind (decision 0013's example shape), for the unit tests and the screenshot page.
import type { ChatTurn, Proposal } from './agent';

export const DID = 'adeefbbcc17559fc';

const base = { chat_id: 'c3f9a1b2c4d5', model: 'rules', cost_usd: 0, latency_s: 0.3 };

export const answerTurn: ChatTurn = {
  ...base,
  turn: 1,
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
  turn: 3,
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

export const conflictTurn: ChatTurn = {
  ...base,
  turn: 4,
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
  turn: 5,
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
  turn: 2,
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
  turn: 6,
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
        area_before_m2: null,
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
