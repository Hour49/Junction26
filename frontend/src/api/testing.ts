// Hand-made #142 check fixtures (shared.md "Checks and issues"), for tests only, until #139's fixtures land.
// Synthetic: the clause texts are placeholders, not quotes of any law.
import type { Clause, DrawingChecks, ProjectChecks, RulePack } from './types';

const P = '5e0c1a2b3d4f';
const A = 'adeefbbcc17559fc';
const B = '6d153ea15dca9ab4';

const doorClause: Clause = {
  ref: 'Test § 1',
  url: 'https://example.org/test-rule-pack#door',
  quote: 'Testilauseke: oven vapaa leveys.',
  quote_en: 'Test clause: the clear width of a door.',
};
const roomClause: Clause = {
  ref: 'Test § 2',
  url: 'https://example.org/test-rule-pack#room',
  quote: 'Test clause: the floor area of a room.',
  quote_en: null,
};

export const rulePackFi: RulePack = {
  id: 'fi',
  country: 'FI',
  country_name: 'Finland',
  name: 'Test accessibility basics',
  law: 'Test law',
  version: '2026-11',
  note: 'A pre-check of a few rules, not a compliance certificate.',
  rules: [
    {
      id: 'door-width',
      title: 'Door clear width',
      op: '>=',
      comparison: 'ge',
      comparison_text: 'at least',
      limit: 0.8,
      unit: 'm',
      applies_to: ['door'],
      clause: doorClause,
    },
    {
      id: 'room-area',
      title: 'Room floor area',
      op: '>=',
      comparison: 'ge',
      comparison_text: 'at least',
      limit: 7,
      unit: 'm2',
      applies_to: ['bedroom'],
      clause: roomClause,
    },
  ],
};

export const drawingChecks: DrawingChecks = {
  drawing_id: A,
  pack: 'fi',
  note: rulePackFi.note,
  status: 'fail',
  rules: [
    {
      rule_id: 'door-width',
      title: 'Door clear width',
      status: 'fail',
      why: 'One door is narrower than the limit; widths are measured from the door symbol box.',
      clause: doorClause,
      results: [
        {
          id: 'door-width:d1',
          rule_id: 'door-width',
          status: 'pass',
          subject: { kind: 'element', ref: 'd1', label: 'door 1' },
          value: 0.9,
          limit: 0.8,
          unit: 'm',
          comparison: 'ge',
          comparison_text: 'at least',
          why: 'Measured 0.90 m from the door symbol box.',
          mark_id: 'm1',
          quantity: 'count:door',
          marks: [
            {
              page: 1,
              box: [0.1, 0.2, 0.15, 0.25],
              polygon: null,
              ref: 'd1',
              label: '1',
              role: 'subject',
            },
          ],
        },
        {
          id: 'door-width:d2',
          rule_id: 'door-width',
          status: 'fail',
          subject: { kind: 'element', ref: 'd2', label: 'door 2' },
          value: 0.75,
          limit: 0.8,
          unit: 'm',
          comparison: 'ge',
          comparison_text: 'at least',
          why: 'Measured 0.75 m from the door symbol box, under 0.80 m.',
          mark_id: 'm2',
          quantity: 'count:door',
          marks: [
            {
              page: 1,
              box: [0.4, 0.2, 0.45, 0.25],
              polygon: null,
              ref: 'd2',
              label: '2',
              role: 'subject',
            },
          ],
        },
        {
          id: 'door-width:d3',
          rule_id: 'door-width',
          status: 'cannot_tell',
          subject: { kind: 'element', ref: 'd3', label: 'door 3' },
          value: null,
          limit: 0.8,
          unit: 'm',
          comparison: 'ge',
          comparison_text: 'at least',
          why: 'The sheet has no scale, so the width cannot be measured.',
          mark_id: null,
          quantity: null,
          marks: [],
        },
      ],
    },
  ],
};

export const projectChecks: ProjectChecks = {
  project_id: P,
  pack: 'fi',
  note: rulePackFi.note,
  drawings: [
    drawingChecks,
    { drawing_id: B, pack: 'fi', note: rulePackFi.note, status: 'pass', rules: [] },
  ],
};
