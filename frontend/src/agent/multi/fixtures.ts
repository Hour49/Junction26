// A proposal with its services follow-up, in the shape of docs/specs/backend/services-follow.md "API": the edit
// card fixture's wall W4 (x 0.40 to 0.41, y 0.20 to 0.30) with a ventilation model that has every status.
import type { Proposal } from '../agent';
import { proposal } from '../fixtures';
import type { Lane, LanePicture, ServicesFollow } from './services';

const none = { follows: 0, stays: 0, needs_decision: 0, cut_off: 0, new_run_m: 0 };

export const ventilation: Lane = {
  discipline: 'ventilation',
  status: 'checked',
  source: 'ventilation.ifc',
  reason: null,
  elements: 625,
  line: 'Ventilation: 1 to re-seat, 1 fire damper, 1 cut off, 1 system passing through.',
  summary: { follows: 1, stays: 2, needs_decision: 1, cut_off: 1, new_run_m: 1.4 },
  marks: [
    {
      ref: 'V1',
      global_id: 'guid-V1',
      kind: 'air terminal',
      label: 'air terminal, ø250, Supply',
      line: [],
      at: [0.398, 0.25],
    },
    {
      ref: 'V2',
      global_id: 'guid-V2',
      kind: 'duct',
      label: 'duct, ø250, Extract',
      line: [
        [0.35, 0.26],
        [0.47, 0.26],
      ],
      at: null,
    },
    {
      ref: 'V3',
      global_id: 'guid-V3',
      kind: 'fire damper',
      label: 'fire damper, Extract',
      line: [],
      at: [0.405, 0.28],
    },
    {
      ref: 'V4',
      global_id: 'guid-V4',
      kind: 'duct',
      label: 'duct, ø250, Supply',
      line: [
        [0.33, 0.22],
        [0.33, 0.29],
      ],
      at: null,
    },
    {
      ref: 'V5',
      global_id: 'guid-V5',
      kind: 'air terminal',
      label: 'air terminal, ø125, Supply',
      line: [],
      at: [0.47, 0.23],
    },
    {
      ref: 'V6',
      global_id: 'guid-V6',
      kind: 'duct',
      label: 'duct, ø125, Supply',
      line: [],
      at: [0.36, 0.22],
    },
  ],
  actions: [
    {
      id: 'a1',
      status: 'stays',
      code: 'through',
      label: '1 duct of Extract passes through the removed wall and stays where it is.',
      refs: ['V2', 'V3'],
      system: 'Extract',
      moved_to: null,
      paths: [],
    },
    {
      id: 'a2',
      status: 'follows',
      code: 'reseat',
      label:
        'The air terminal in Bagno 1.01 hangs on the removed wall: re-seated on the nearest free kept wall, 1.4 m away, with about 1.4 m of new connection (Supply). An estimate, not a routed design.',
      refs: ['V1'],
      system: null,
      moved_to: [0.398, 0.202],
      paths: [
        [
          [0.398, 0.25],
          [0.398, 0.202],
        ],
      ],
    },
    {
      id: 'a3',
      status: 'needs_decision',
      code: 'fire_damper',
      label:
        'A fire damper sits in this wall: the wall is probably a fire compartment boundary, which this check cannot confirm.',
      refs: ['V3'],
      system: null,
      moved_to: null,
      paths: [],
    },
    {
      id: 'a4',
      status: 'cut_off',
      code: 'cut_off',
      label: '1 air terminal of Supply is cut off from the rest of its system.',
      refs: ['V5'],
      system: 'Supply',
      moved_to: null,
      paths: [],
    },
    {
      id: 'a5',
      status: 'stays',
      code: 'tally',
      label: 'The merged room has 3 air terminals (2 from Bagno 1.01 + 1 from Stanza 1.02).',
      refs: [],
      system: null,
      moved_to: null,
      paths: [],
    },
  ],
};

export const services: ServicesFollow = {
  storey: 'Ground floor',
  disciplines: [
    {
      discipline: 'plumbing',
      status: 'checked',
      source: 'plumbing.ifc',
      reason: null,
      elements: 562,
      line: 'Plumbing: nothing of this model is on, in or through the changed walls.',
      summary: { ...none, stays: 1 },
      marks: [],
      actions: [
        {
          id: 'a1',
          status: 'stays',
          code: 'tally',
          label: 'The merged room has 2 washbasins (2 from Bagno 1.01).',
          refs: [],
          system: null,
          moved_to: null,
          paths: [],
        },
      ],
    },
    ventilation,
    {
      discipline: 'heating',
      status: 'not_aligned',
      source: 'heating.ifc',
      reason: 'its rooms miss this sheet by 0.31 m',
      elements: 0,
      line: 'Heating: not checked, its rooms miss this sheet by 0.31 m.',
      summary: none,
      marks: [],
      actions: [],
    },
    {
      discipline: 'electrical',
      status: 'no_model',
      source: null,
      reason: 'this project has no electrical model',
      elements: 0,
      line: 'Electrical: not checked, this project has no electrical model.',
      summary: none,
      marks: [],
      actions: [],
    },
  ],
  unknowns: ['The services are not checked against each other in 3D (a pipe against a duct).'],
  credits: ['Services model: Example University (MIT License)'],
};

export const followed: Proposal = { ...proposal, services };

/** pics-edit-follow W3: a heating lane read from the floor's heating picture (another sheet), with the edit and its
 * marks placed on that sheet: wall W4 lies at x 0.45 to 0.46, y 0.30 to 0.40 there. */
export const PIC = 'pic0heating0001';
export const heatingPicture: Lane & { picture: LanePicture } = {
  discipline: 'heating',
  status: 'checked',
  source: 'heating plan (picture)',
  reason: null,
  elements: 14,
  line: 'Heating: 1 radiator to re-seat, 1 pipe passing through.',
  summary: { ...none, needs_decision: 1, stays: 1 },
  marks: [
    { ref: 'H1', global_id: '', kind: 'radiator', label: 'radiator', line: [], at: [0.398, 0.24] },
    {
      ref: 'H2',
      global_id: '',
      kind: 'pipe',
      label: 'pipe, heating flow',
      line: [
        [0.36, 0.27],
        [0.45, 0.27],
      ],
      at: null,
    },
  ],
  actions: [
    {
      id: 'h1',
      status: 'needs_decision',
      code: 'reseat',
      label:
        'The radiator on the removed wall has to move; where to and how to reconnect are not shown on a picture.',
      refs: ['H1'],
      system: null,
      moved_to: null,
      paths: [],
    },
    {
      id: 'h2',
      status: 'stays',
      code: 'through',
      label: 'The heating flow pipe crossing the wall is now open to the merged room.',
      refs: ['H2'],
      system: 'heating flow',
      moved_to: null,
      paths: [],
    },
  ],
  picture: {
    drawing_id: PIC,
    page: 1,
    pairing: {
      drawing_id: PIC,
      page: 1,
      paired_by: 'metadata',
      reason: "same floor in the title block: 'EG' on both",
      score: null,
    },
    removed: [
      [
        [0.45, 0.3],
        [0.46, 0.3],
        [0.46, 0.4],
        [0.45, 0.4],
      ],
    ],
    added: [],
    marks: [
      { ref: 'H1', line: [], at: [0.448, 0.34] },
      {
        ref: 'H2',
        line: [
          [0.41, 0.37],
          [0.5, 0.37],
        ],
        at: null,
      },
    ],
  },
};

export const pictured: Proposal = {
  ...proposal,
  services: { ...services, disciplines: [heatingPicture, ventilation] },
};
