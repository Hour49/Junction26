// EN-69, EN-70: the card mounts DoubleCheck (double-check.md "Mounting"); here it is a props-recording double.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { AnswerView } from '../api';
import { answer, answerArea, answerRefused, drawing, project } from '../api/fixtures';
import { mockApi } from '../test/mockApi';
import { EngineerPage } from './EngineerPage';
import { answerEdited } from './testing';

type Props = {
  answer: AnswerView;
  projectId: string;
  drawingId: string;
  onChanged: (answer: AnswerView) => void;
};
const mounts = vi.hoisted(() => [] as Props[]);

vi.mock('../doublecheck/DoubleCheck', () => ({
  DoubleCheck: (props: Props) => {
    mounts.push(props);
    return <div data-testid="double-check" />;
  },
}));

const PROJECT = '5e0c1a2b3d4f';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  mounts.length = 0;
});

function open(...bodies: AnswerView[]) {
  const queue = [...bodies];
  const api = mockApi({
    [`GET /api/drawings/${drawing.id}`]: drawing,
    [`GET /api/projects/${PROJECT}`]: project,
    'POST /api/ask': () => queue.shift(),
  });
  render(<EngineerPage projectId={PROJECT} drawingId={drawing.id} />);
  return api;
}

async function ask(question: string) {
  const input = await screen.findByRole('textbox', { name: 'Question' });
  fireEvent.change(input, { target: { value: question } });
  fireEvent.submit(input.closest('form') as HTMLFormElement);
  const turn = await screen.findByRole('article', { name: question });
  await within(turn).findByText(/^(Cost |I can't answer)/);
  return turn;
}

const last = () => mounts.at(-1) as Props;

it('EN-70 an answer card mounts DoubleCheck once, right after the value row, with its answer and ids', async () => {
  open(answer);
  const t = await ask(answer.question);
  const dc = within(t).getAllByTestId('double-check');
  expect(dc).toHaveLength(1);
  expect(dc[0]?.previousElementSibling?.className).toBe('en-value-row');
  expect(last().answer).toEqual(answer);
  expect(last().projectId).toBe(PROJECT);
  expect(last().drawingId).toBe(answer.drawing_id);
});

it('EN-70 a refusal mounts no DoubleCheck', async () => {
  open(answerRefused);
  const t = await ask(answerRefused.question);
  expect(within(t).queryByTestId('double-check')).toBeNull();
});

it("EN-70 onChanged replaces that turn's answer only; the card sends nothing itself", async () => {
  const api = open(answerArea, answer);
  const area = await ask(answerArea.question);
  const doors = await ask(answer.question);
  const posts = api.calls.filter((c) => c.method === 'POST').length;
  const doorMount = mounts.filter((m) => m.answer.question === answer.question).at(-1) as Props;
  act(() => {
    doorMount.onChanged(answerEdited);
  });
  expect(within(doors).getByTestId('answer-value').textContent).toBe('1');
  expect(within(doors).getByText('Changed in review, was 2')).toBeTruthy();
  expect(last().answer).toEqual(answerEdited);
  expect(within(area).getByTestId('answer-value').textContent).toBe('52.27 m²');
  expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(posts);
});

it('EN-69 the card shows no check line of its own: DoubleCheck owns the reason', async () => {
  const checked = {
    ...answer,
    check: { reason: 'Two readers disagree on door m2.', disputed: [] },
  };
  open(checked);
  const t = await ask(answer.question);
  expect(t.querySelector('[data-pending="AnswerView.check"]')).toBeNull();
  expect(t.textContent).not.toContain('Two readers disagree on door m2.');
});
