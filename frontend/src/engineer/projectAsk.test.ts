import { afterEach, expect, it } from 'vitest';
import { cleanup } from '@testing-library/react';
import type { AnswerView } from '../api';
import { answer, answerArea, answerRefused, project } from '../api/fixtures';
import { mockApi } from '../test/mockApi';
import { askable, askProject, starters } from './projectAsk';

const PID = project.id;
const ids = project.drawings.map((d) => d.drawing_id);

afterEach(() => {
  cleanup();
});

/** POST /api/ask answered per drawing id: an answer body, or a status for a failure. */
function per(bodies: Record<string, AnswerView | number>) {
  return mockApi({
    'POST /api/ask': (c: { body: unknown }) => {
      const { drawing_id: id } = c.body as { drawing_id: string };
      const b = bodies[id] ?? answerRefused;
      return typeof b === 'number'
        ? { status: b, body: { detail: 'internal error', code: 'internal' } }
        : b;
    },
  });
}

it('CH-9 askable: ready and flagged drawings, not queued, running, text_only or set_aside', () => {
  const list = [
    ...project.drawings,
    { ...project.drawings[0], drawing_id: 'q', state: 'queued' },
    { ...project.drawings[0], drawing_id: 't', state: 'text_only' },
  ] as typeof project.drawings;
  expect(askable(list).map((d) => d.drawing_id)).toEqual(ids);
});

it("CH-9 one request per drawing with the project; parts named by this project's files, answering first", async () => {
  const api = per({
    [ids[3] as string]: answerArea,
    [ids[1] as string]: answer,
    [ids[2] as string]: 500,
  });
  const got = await askProject(PID, project.drawings, 'How many doors are there?');
  expect(api.calls.map((c) => c.body)).toEqual(
    ids.map((id) => ({ drawing_id: id, question: 'How many doors are there?', project_id: PID })),
  );
  expect(got.question).toBe('How many doors are there?');
  // answering (drawing order), then refused (drawing order); the failed request is no part
  expect(got.parts.map((p) => p.drawing_id)).toEqual([ids[1], ids[3], ids[0], ids[4]]);
  expect(got.parts.map((p) => p.name)).toEqual([1, 3, 0, 4].map((i) => project.drawings[i]?.file));
  // two drawings answer: never added up (Bogdan #14 c6875696652)
  expect(got.total).toBeNull();
  expect(got.total_note).toBe(
    'These drawings may show the same rooms, so the numbers are not added up.',
  );
});

it('CH-9 the total: only when exactly one drawing answers; two in one unit are not added up', async () => {
  per({ [ids[0] as string]: answer });
  const one = await askProject(PID, project.drawings, 'How many doors are there?');
  expect(one.total).toBe(2);
  expect(one.total_note).toBeNull();
  per({ [ids[0] as string]: answer, [ids[1] as string]: answer });
  const two = await askProject(PID, project.drawings, 'How many doors are there?');
  expect(two.total).toBeNull();
  expect(two.total_note).toBe(
    'These drawings may show the same rooms, so the numbers are not added up.',
  );
});

it('CH-9 nothing answers: every part refused, no total', async () => {
  per({});
  const got = await askProject(PID, project.drawings, 'What colour is the roof?');
  expect(got.parts).toHaveLength(ids.length);
  expect(got.parts.every((p) => p.answer.refusal !== null)).toBe(true);
  expect(got.total).toBeNull();
  expect(got.total_note).toBeNull();
});

it('CH-9 every request fails: rejects with the first error; no drawing: rejects with the sentence', async () => {
  per(Object.fromEntries(ids.map((id) => [id, 500])));
  await expect(askProject(PID, project.drawings, 'q')).rejects.toMatchObject({ status: 500 });
  await expect(askProject(PID, [], 'q')).rejects.toThrow(
    'No drawing in this project can be asked yet.',
  );
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
