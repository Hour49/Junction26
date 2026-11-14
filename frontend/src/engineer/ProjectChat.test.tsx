import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { ProjectAnswer, ProjectView } from '../api';
import { answerArea, answerRefused, drawing, error, project, projectAsk } from '../api/fixtures';
import { mockApi, never } from '../test/mockApi';
import { ProjectChat } from './ProjectChat';

const PID = project.id;
const ROUTE = `GET /api/projects/${PID}`;
const ids = project.drawings.map((d) => d.drawing_id);
const N = ids.length; // every drawing of project.json is ready or flagged
const ASK = `POST /api/projects/${PID}/ask`;
const [flatA, flatB, refusedPart] = projectAsk.parts as [
  ProjectAnswer['parts'][number],
  ProjectAnswer['parts'][number],
  ProjectAnswer['parts'][number],
];
/** project_ask.json with only flat-a answering: a total of 2 doors (CH-4). */
const oneAnswers: ProjectAnswer = {
  ...projectAsk,
  parts: [flatA, refusedPart],
  total: 2,
  total_unit: 'count',
  total_note: 'The total is the one drawing that answered; 1 drawing has no reader for it.',
};
/** Every drawing refuses (CH-6). */
const noneAnswers: ProjectAnswer = {
  ...projectAsk,
  parts: [{ ...refusedPart, answer: { ...answerRefused, drawing_id: refusedPart.drawing_id } }],
  total: null,
  total_unit: null,
  total_note: 'No drawing answered it: 1 drawing has no reader for it.',
};

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
});

/** Each drawing answers GET with drawing.json (its 3 suggestions) unless `drawings` says otherwise. */
const drawingRoutes = (body: unknown = drawing) =>
  Object.fromEntries(ids.map((id) => [`GET /api/drawings/${id}`, body]));

/** The project ask answers `reply` (a status number is a failure), the question echoed. */
function open(
  reply: ProjectAnswer | number = noneAnswers,
  proj: unknown = project,
  drawings: Record<string, unknown> = drawingRoutes(),
) {
  const api = mockApi({
    [ROUTE]: proj,
    ...drawings,
    [ASK]: (c: { body: unknown }) => {
      const { question } = c.body as { question: string };
      if (typeof reply === 'number')
        return { status: reply, body: { detail: 'internal error', code: 'internal' } };
      return { ...reply, question };
    },
  });
  render(<ProjectChat projectId={PID} />);
  return api;
}

async function ask(question: string) {
  const input = await screen.findByRole('textbox', { name: 'Question' });
  fireEvent.change(input, { target: { value: question } });
  fireEvent.submit(input.closest('form') as HTMLFormElement);
  return screen.findByRole('article', { name: question });
}
const posts = (api: ReturnType<typeof mockApi>) => api.calls.filter((c) => c.method === 'POST');

it('CH-1 the project is requested once; loading while pending; a 404 shows the error and the way back', async () => {
  const api = open();
  await screen.findByRole('heading', { level: 1, name: project.name });
  const gets = api.calls.filter((c) => c.method === 'GET').map((c) => c.url);
  expect(gets.filter((u) => u.startsWith('/api/projects/'))).toEqual([`/api/projects/${PID}`]);
  // the starter questions: each askable drawing once, in this project
  await waitFor(() => {
    expect(
      api.calls
        .filter((c) => c.url.startsWith('/api/drawings/'))
        .map((c) => c.url)
        .sort(),
    ).toEqual(ids.map((id) => `/api/drawings/${id}?project=${PID}`).sort());
  });
  cleanup();
  open(noneAnswers, () => never());
  expect(screen.getByRole('status')).toBeTruthy();
  cleanup();
  open(noneAnswers, { status: 404, body: error });
  expect(await screen.findByRole('link', { name: 'Back to the project' })).toBeTruthy();
});

it('CH-2 the empty chat (Tudor 12:45): heading, the ask bar, then 3 starter chips; no line, no drawing', async () => {
  open();
  await screen.findByRole('heading', { level: 1, name: project.name });
  const chips = await screen.findByRole('group', { name: 'Suggested questions' });
  expect(
    within(chips)
      .getAllByRole('button')
      .map((b) => b.textContent),
    // drawing.json's own three, a door count first
  ).toEqual([
    'How many doors are there?',
    'What is the net floor area of all indoor rooms in m²?',
    'How many windows are there?',
  ]);
  const form = screen.getByRole('textbox', { name: 'Question' }).closest('form') as HTMLFormElement;
  // the bar first, the chips directly under it
  expect(form.compareDocumentPosition(chips) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(document.querySelector('.en-chat--empty')).toBeTruthy();
  expect(screen.queryByText(/Ask anything about/)).toBeNull();
  expect(document.querySelector('img, figure')).toBeNull();
});

it('CH-11 a chip asks the project; then the thread, the bar at the bottom, no chips', async () => {
  const api = open(oneAnswers);
  const q = drawing.suggestions[0]?.question ?? '';
  fireEvent.click(await screen.findByRole('button', { name: q }));
  await screen.findByRole('article', { name: q });
  expect(posts(api).map((c) => c.body)).toEqual([{ question: q }]);
  expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
  expect(document.querySelector('.en-chat--empty')).toBeNull();
  const thread = screen.getByRole('region', { name: 'Chat' });
  const form = screen.getByRole('textbox', { name: 'Question' }).closest('form') as HTMLFormElement;
  expect(thread.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it('CH-12 fewer suggestions give fewer chips; none (or failed loads) give none and the bar still asks', async () => {
  const one = { ...drawing, suggestions: drawing.suggestions.slice(0, 1) };
  open(noneAnswers, project, {
    ...drawingRoutes({ ...drawing, suggestions: [] }),
    [`GET /api/drawings/${ids[2] as string}`]: one,
  });
  const chips = await screen.findByRole('group', { name: 'Suggested questions' });
  expect(within(chips).getAllByRole('button')).toHaveLength(1);
  cleanup();
  open(
    noneAnswers,
    project,
    drawingRoutes({ status: 500, body: { detail: 'internal error', code: 'internal' } }),
  );
  await screen.findByRole('heading', { level: 1, name: project.name });
  expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
  expect(screen.getByRole('textbox', { name: 'Question' })).toBeTruthy();
});

it('CH-3 a question is one POST to the project ask; Reading N drawings… while pending', async () => {
  const api = mockApi({ [ROUTE]: project, ...drawingRoutes(), [ASK]: () => never() });
  render(<ProjectChat projectId={PID} />);
  const t = await ask('How many doors are there?');
  expect(within(t).getByText(`Reading ${String(N)} drawings…`)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' }).disabled).toBe(true);
  expect(posts(api).map((c) => [c.url, c.body])).toEqual([
    [`/api/projects/${PID}/ask`, { question: 'How many doors are there?' }],
  ]);
});

/** Asks and returns the turn once its parts card shows (the pending article is replaced by it). */
async function answered(question: string) {
  await ask(question);
  return waitFor(() => {
    const t = screen.getByRole('article', { name: question });
    expect(t.querySelector('.en-chatcard')).toBeTruthy();
    return t;
  });
}

const line = (turn: HTMLElement, name: string) =>
  within(turn).getByText(name, { selector: '.en-part-name' }).closest('li') as HTMLElement;

it('CH-4 one drawing answers: the total, the note, one line <name>: <value> with Show it on <name>; no plan', async () => {
  open(oneAnswers);
  const turn = await answered('How many doors are there?');
  expect((await within(turn).findByTestId('answer-value')).textContent).toBe('2');
  expect(within(turn).getByText(oneAnswers.total_note)).toBeTruthy();
  const li = line(turn, flatA.name);
  expect(li.textContent).toContain(`${flatA.name}: 2`);
  const show = within(li).getByRole('link', { name: `Show it on ${flatA.name}` });
  expect(show.getAttribute('href')).toBe(`#/p/${PID}/d/${flatA.drawing_id}/engineer`);
  expect(within(turn).getAllByRole('listitem')).toHaveLength(1);
  expect(turn.querySelector('figure, img')).toBeNull();
  expect(turn.textContent).not.toContain("I can't answer");
  expect(within(turn).queryByText(/^Sure/)).toBeNull();
});

it('CH-5 project_ask.json: two drawings answer, no total, its note, then a line per drawing', async () => {
  open(projectAsk);
  const turn = await answered('How many doors are there?');
  expect(within(turn).getByText(projectAsk.total_note)).toBeTruthy();
  expect(within(turn).queryByTestId('answer-value')).toBeNull();
  for (const p of [flatA, flatB]) {
    expect(line(turn, p.name).textContent).toContain(`${p.name}: 2`);
    expect(
      within(line(turn, p.name)).getByRole('link', { name: `Show it on ${p.name}` }),
    ).toBeTruthy();
  }
  expect(within(turn).getAllByRole('listitem')).toHaveLength(2);
});

it('CH-13 the total in total_unit; the Sure badge only when total_sure', async () => {
  const area: ProjectAnswer = {
    ...oneAnswers,
    parts: [{ ...flatA, answer: answerArea }],
    total: 52.27,
    total_unit: 'm2',
    total_sure: true,
  };
  open(area);
  const turn = await answered('What is the net floor area of all indoor rooms in m²?');
  expect(within(turn).getByTestId('answer-value').textContent).toBe('52.27 m²');
  const badge = within(turn).getByText(/^Sure/);
  expect(badge.getAttribute('title')).toMatch(/^Certified: /);
});

it('CH-6 nobody answers: one refusal for the project; its questions ask every drawing again', async () => {
  const api = open(noneAnswers);
  const turn = await ask('What colour is the roof?');
  expect(await within(turn).findByText("I can't answer that from these drawings.")).toBeTruthy();
  expect(within(turn).getByText(answerRefused.refusal?.text ?? '')).toBeTruthy();
  const q = answerRefused.refusal?.can_answer[0]?.question ?? '';
  fireEvent.click(within(turn).getByRole('button', { name: q }));
  await screen.findByRole('article', { name: q });
  expect(posts(api).map((c) => c.body)).toEqual([
    { question: 'What colour is the roof?' },
    { question: q },
  ]);
});

it.each([500, 409])(
  'CH-7 the ask fails (%i): the error turn; Try again asks again',
  async (status) => {
    const api = open(status);
    const turn = await ask('How many doors are there?');
    expect(await within(turn).findByText(/The question could not be answered/)).toBeTruthy();
    fireEvent.click(within(turn).getByRole('button', { name: 'Try again' }));
    await within(turn).findByText(/The question could not be answered/);
    expect(posts(api)).toHaveLength(2);
  },
);

it('CH-8 no askable drawing: the sentence, Ask disabled', async () => {
  const none: ProjectView = {
    ...project,
    drawings: project.drawings.map((d) => ({ ...d, state: 'set_aside' as const })),
  };
  open(noneAnswers, none);
  expect(await screen.findByText('No drawing in this project can be asked yet.')).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' }).disabled).toBe(true);
});
