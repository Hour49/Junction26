import { expect, it } from 'vitest';
import { project, projectAsk } from '../api/fixtures';
import { askable, followUps, orderParts, starters } from './projectAsk';

const ids = project.drawings.map((d) => d.drawing_id);

it('CH-9 askable: ready and flagged drawings, not queued, running, text_only or set_aside', () => {
  const list = [
    ...project.drawings,
    { ...project.drawings[0], drawing_id: 'q', state: 'queued' },
    { ...project.drawings[0], drawing_id: 't', state: 'text_only' },
  ] as typeof project.drawings;
  expect(askable(list).map((d) => d.drawing_id)).toEqual(ids);
});

const s = (quantity: string, question: string) => ({ quantity, question, label: quantity });

it('CH-12 starters: up to 3 distinct questions, a door count, an area and a window count first', () => {
  const flatA = [
    s('area:room|indoor', 'What is the net floor area of all indoor rooms in m²?'),
    s('door', 'How many doors are there?'),
    s('window', 'How many windows are there?'),
    s('toilet', 'How many toilets are there?'),
  ];
  const ifc = [
    s('door|model', 'How many doors are there in the building model?'),
    s('door', 'How many doors are there?'),
  ];
  expect(starters([flatA, [], ifc]).map((x) => x.question)).toEqual([
    'How many doors are there?',
    'What is the net floor area of all indoor rooms in m²?',
    'How many windows are there?',
  ]);
  expect(starters([[s('wall', 'How many walls are there?')], []]).map((x) => x.question)).toEqual([
    'How many walls are there?',
  ]);
  expect(starters([[], []])).toEqual([]);
});

it('CH-30 orderParts: answering parts only, sheets that are not floor plans first, each group in API order', () => {
  type Part = (typeof projectAsk.parts)[number];
  const [a, b, refused] = projectAsk.parts as [Part, Part, Part];
  const c = { ...b, drawing_id: 'c0', name: 'sections/section-a.png' };
  const file = (drawing_id: string, cls: 'floor_plan' | 'other_drawing' | 'not_drawing' | null) =>
    ({
      ...project.files[0],
      drawing_id,
      triage: cls && { ...(project.files[0]?.triage ?? {}), class: cls },
    }) as (typeof project.files)[number];
  const files = [
    file(a.drawing_id, null),
    file(b.drawing_id, 'not_drawing'),
    file('c0', 'other_drawing'),
  ];
  expect(orderParts([a, refused, b, c], files).map((p) => p.drawing_id)).toEqual([
    b.drawing_id,
    'c0',
    a.drawing_id,
  ]);
  expect(orderParts([a, b], [file(b.drawing_id, 'floor_plan')]).map((p) => p.drawing_id)).toEqual([
    a.drawing_id,
    b.drawing_id,
  ]);
});

it('CH-36 followUps: up to 3 unasked questions, the first of each kind first, then the rest, no repeats', () => {
  const flatA = [
    s('area:room|indoor', 'What is the net floor area of all indoor rooms in m²?'),
    s('door', 'How many doors are there?'),
    s('window', 'How many windows are there?'),
    s('toilet', 'How many toilets are there?'),
  ];
  const flatB = [
    s('door', 'How many doors are there?'),
    s('area:room|name=kitchen', 'What is the area of the kitchen?'),
  ];
  const q = (xs: { question: string }[]) => xs.map((x) => x.question);
  expect(q(followUps([flatA, flatB], [' How many doors are there? ']))).toEqual([
    'What is the net floor area of all indoor rooms in m²?',
    'How many windows are there?',
    'How many toilets are there?',
  ]);
  expect(q(followUps([flatA, flatB], q(flatA)))).toEqual(['What is the area of the kitchen?']);
  expect(followUps([flatA], q(flatA))).toEqual([]);
});
