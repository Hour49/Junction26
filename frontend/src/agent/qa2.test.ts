// QA rerun minors on agent/law-check (.agents/qa-law/rerun-*.md), each test named by its QA id.
import { expect, it } from 'vitest';
import { badgeGroups, inlineOf, type RoomChange } from './agent';

const rect = (x0: number, y0: number, x1: number, y1: number): RoomChange['polygon'] => [
  [x0, y0],
  [x1, y0],
  [x1, y1],
  [x0, y1],
];
const room = (id: string, polygon: RoomChange['polygon']): RoomChange => ({
  id,
  label: id,
  polygon,
  area_before_m2: 1,
  area_after_m2: 1,
  was: [],
});

it('lawai-4 inlineOf: *italic* and _italic_ become em, snake_case and a lone * stay text', () => {
  expect(inlineOf('*BBV I* and _Unofficial translation_ of snake_case_name, 2 * 3')).toEqual([
    { kind: 'em', text: 'BBV I' },
    { kind: 'text', text: ' and ' },
    { kind: 'em', text: 'Unofficial translation' },
    { kind: 'text', text: ' of snake_case_name, 2 * 3' },
  ]);
  expect(inlineOf('**bold** then *it*')).toEqual([
    { kind: 'b', text: 'bold' },
    { kind: 'text', text: ' then ' },
    { kind: 'em', text: 'it' },
  ]);
  expect(inlineOf('*<img src=x onerror=alert(1)>*')).toEqual([
    { kind: 'em', text: '<img src=x onerror=alert(1)>' }, // rendered as React text: no HTML
  ]);
});

it('rerun-lawcheck-1 badgeGroups: a box cut from a room bottom edge stacks both badges in one group', () => {
  // Stanza 1.02 shrunk to its left part, a storage room cut from its right: both end at y 0.40
  const stanza = room('Stanza 1.02', rect(0.5, 0.27, 0.6, 0.4));
  const storage = room('Storage', rect(0.6, 0.27, 0.655, 0.4));
  const far = room('Bagno', rect(0.1, 0.7, 0.2, 0.8));
  const groups = badgeGroups([storage, stanza, far]);
  expect(groups.map((g) => g.rooms.map((r) => r.id))).toEqual([
    ['Storage', 'Stanza 1.02'],
    ['Bagno'],
  ]);
  expect(groups[0]).toMatchObject({ y: 0.4 });
  expect(groups[1]?.x).toBeCloseTo(0.15);
  expect(groups[1]?.y).toBe(0.8);
});
