// A radiator moved to another wall of its room, in the shape of docs/specs/backend/services-model.md SV-28: the
// branch E31 removed, a new run N1, the main E40 halved at the new tee (shown as neither removed nor added).
import type { Proposal } from '../agent';
import { proposal } from '../fixtures';
import type { ServicesChange } from './change';

export const PICTURE = '/api/projects/p-1/drawings/d-svc/services/L2.png';

export const moved: ServicesChange = {
  op: 'move_terminal',
  storey: 'L2',
  based_on: [],
  picture: PICTURE,
  moved: [
    {
      id: 'E12',
      label: 'Radiator 22-600',
      from: [0.41, 0.32],
      to: [0.47, 0.38],
      to_m: [12.1, 4.3, 0.15],
    },
  ],
  removed: [
    {
      id: 'E31',
      label: 'Pipe DN15, 2.00 m',
      system: 'Heating 1',
      polyline: [
        [0.4, 0.31],
        [0.44, 0.31],
      ],
    },
    {
      id: 'E40',
      label: 'Pipe DN20, 4.00 m',
      system: 'Heating 1',
      polyline: [
        [0.3, 0.5],
        [0.5, 0.5],
      ],
    },
  ],
  added: [
    {
      id: 'N1',
      label: 'Pipe DN15, 6.50 m',
      system: 'Heating 1',
      polyline: [
        [0.4, 0.31],
        [0.47, 0.31],
        [0.47, 0.37],
      ],
    },
    {
      id: 'N2',
      label: 'Pipe DN20, 1.50 m',
      system: 'Heating 1',
      polyline: [
        [0.3, 0.5],
        [0.38, 0.5],
      ],
    },
    {
      id: 'N3',
      label: 'Pipe DN20, 2.50 m',
      system: 'Heating 1',
      polyline: [
        [0.38, 0.5],
        [0.5, 0.5],
      ],
    },
  ],
  facts: [
    { what: 'pipe length', system: 'Heating 1', size: 'DN15', unit: 'm', before: 38.5, after: 43 },
    { what: 'pipe_fitting count', system: null, size: null, unit: 'count', before: 12, after: 13 },
  ],
  checks: [
    { code: 'connected', ok: true, text: 'The heating network is still in one piece.' },
    { code: 'no_door', ok: false, text: 'The new run passes a door.' },
  ],
  flags: [
    {
      code: 'not_sized',
      text: 'Sizes are copied from the old branch. Flow, pressure and clashes with other services are not checked.',
    },
  ],
  unknowns: ['Whether the new run clashes with other services: not checked.'],
  patch: {
    added: [],
    changed: [],
    connections_added: [],
    connections_removed: [],
    moved: [],
    removed: [],
  },
};

/** The proposal as the chat sends it (SV-28): no plan geometry of its own, unknowns and flags copied up. */
export const servicesProposal: Proposal = {
  ...proposal,
  proposal_id: 'p2',
  drawing_id: 'd-svc',
  page: 2,
  removed: [],
  added: [],
  rooms: [],
  law: null,
  unknowns: moved.unknowns,
  flags: moved.flags,
  services_change: moved,
};
