import { expect, it } from 'vitest';
import { project } from '../api/fixtures';
import { askable, starters } from './projectAsk';

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
