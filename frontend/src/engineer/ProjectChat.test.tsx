import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { AnswerView, ProjectView } from '../api';
import { answer, answerArea, answerRefused, drawing, error, project } from '../api/fixtures';
import { mockApi, never } from '../test/mockApi';
import { ProjectChat } from './ProjectChat';

const PID = project.id;
const ROUTE = `GET /api/projects/${PID}`;
const ids = project.drawings.map((d) => d.drawing_id);
const N = ids.length; // every drawing of project.json is ready or flagged

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
});

/** POST /api/ask per drawing id (default: the refusal); a number is a failure with that status. */
/** Each drawing answers GET with drawing.json (its 3 suggestions) unless `drawings` says otherwise. */
const drawingRoutes = (body: unknown = drawing) =>
  Object.fromEntries(ids.map((id) => [`GET /api/drawings/${id}`, body]));

function open(
  bodies: Record<string, AnswerView | number> = {},
  proj: unknown = project,
  drawings: Record<string, unknown> = drawingRoutes(),
) {
  const api = mockApi({
    [ROUTE]: proj,
    ...drawings,
    'POST /api/ask': (c: { body: unknown }) => {
      const { drawing_id: id, question } = c.body as { drawing_id: string; question: string };
      const b = bodies[id] ?? answerRefused;
      if (typeof b === 'number')
        return { status: b, body: { detail: 'internal error', code: 'internal' } };
      return { ...b, question, drawing_id: id };
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
  open({}, () => never());
  expect(screen.getByRole('status')).toBeTruthy();
  cleanup();
  open({}, { status: 404, body: error });
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
  const api = open({ [ids[0] as string]: answer });
  const q = drawing.suggestions[0]?.question ?? '';
  fireEvent.click(await screen.findByRole('button', { name: q }));
  await screen.findByRole('article', { name: q });
  expect(posts(api).filter((c) => (c.body as { question: string }).question === q)).toHaveLength(N);
  expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
  expect(document.querySelector('.en-chat--empty')).toBeNull();
  const thread = screen.getByRole('region', { name: 'Chat' });
  const form = screen.getByRole('textbox', { name: 'Question' }).closest('form') as HTMLFormElement;
  expect(thread.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it('CH-12 fewer suggestions give fewer chips; none (or failed loads) give none and the bar still asks', async () => {
  const one = { ...drawing, suggestions: drawing.suggestions.slice(0, 1) };
  open({}, project, {
    ...drawingRoutes({ ...drawing, suggestions: [] }),
    [`GET /api/drawings/${ids[2] as string}`]: one,
  });
  const chips = await screen.findByRole('group', { name: 'Suggested questions' });
  expect(within(chips).getAllByRole('button')).toHaveLength(1);
  cleanup();
  open(
    {},
    project,
    drawingRoutes({ status: 500, body: { detail: 'internal error', code: 'internal' } }),
  );
  await screen.findByRole('heading', { level: 1, name: project.name });
  expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
  expect(screen.getByRole('textbox', { name: 'Question' })).toBeTruthy();
});

it('CH-3 a question goes to every askable drawing with the project; Reading N drawings… while pending', async () => {
  const api = mockApi({ [ROUTE]: project, ...drawingRoutes(), 'POST /api/ask': () => never() });
  render(<ProjectChat projectId={PID} />);
  const t = await ask('How many doors are there?');
  expect(within(t).getByText(`Reading ${String(N)} drawings…`)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' }).disabled).toBe(true);
  expect(posts(api).map((c) => c.body)).toEqual(
    ids.map((id) => ({ drawing_id: id, question: 'How many doors are there?', project_id: PID })),
  );
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

it('CH-4 one drawing answers: the total, one line <name>: <value> with Show it on <name>; no plan', async () => {
  const id = ids[0] as string;
  const name = project.drawings[0]?.file ?? '';
  open({ [id]: answer });
  const turn = await answered('How many doors are there?');
  expect((await within(turn).findByTestId('answer-value')).textContent).toBe('2');
  const li = line(turn, name);
  expect(li.textContent).toContain(`${name}: 2`);
  const show = within(li).getByRole('link', { name: `Show it on ${name}` });
  expect(show.getAttribute('href')).toBe(`#/p/${PID}/d/${id}/engineer`);
  expect(within(turn).getAllByRole('listitem')).toHaveLength(1);
  expect(turn.querySelector('figure, img')).toBeNull();
  expect(turn.textContent).not.toContain("I can't answer");
});

it('CH-5 two drawings answer: no total, the may-overlap note, then a line per drawing', async () => {
  const [a, b] = [ids[0] as string, ids[1] as string];
  open({ [a]: answer, [b]: answer });
  const turn = await answered('How many doors are there?');
  expect(
    within(turn).getByText(
      'These drawings may show the same rooms, so the numbers are not added up.',
    ),
  ).toBeTruthy();
  expect(within(turn).queryByTestId('answer-value')).toBeNull();
  for (const d of project.drawings.slice(0, 2)) {
    expect(line(turn, d.file).textContent).toContain(`${d.file}: 2`);
    expect(
      within(line(turn, d.file)).getByRole('link', { name: `Show it on ${d.file}` }),
    ).toBeTruthy();
  }
});

it('CH-5 two drawings, different kinds of value: no total, the note, a line each', async () => {
  const [a, b] = [ids[0] as string, ids[4] as string];
  open({ [a]: answer, [b]: answerArea });
  const turn = await answered('How many doors are there?');
  await within(turn).findByText(
    'These drawings may show the same rooms, so the numbers are not added up.',
  );
  expect(within(turn).queryByTestId('answer-value')).toBeNull();
  expect(line(turn, project.drawings[0]?.file ?? '').textContent).toContain(': 2');
  expect(line(turn, project.drawings[4]?.file ?? '').textContent).toContain(': 52.27 m²');
});

it('CH-6 nobody answers: one refusal for the project; its questions ask every drawing again', async () => {
  const api = open();
  const turn = await ask('What colour is the roof?');
  expect(await within(turn).findByText("I can't answer that from these drawings.")).toBeTruthy();
  expect(within(turn).getByText(answerRefused.refusal?.text ?? '')).toBeTruthy();
  const q = answerRefused.refusal?.can_answer[0]?.question ?? '';
  fireEvent.click(within(turn).getByRole('button', { name: q }));
  await screen.findByRole('article', { name: q });
  expect(posts(api).filter((c) => (c.body as { question: string }).question === q)).toHaveLength(N);
});

it('CH-7 every request fails: the error turn; Try again asks every drawing again', async () => {
  const api = open(Object.fromEntries(ids.map((id) => [id, 500])));
  const turn = await ask('How many doors are there?');
  expect(await within(turn).findByText(/The question could not be answered/)).toBeTruthy();
  fireEvent.click(within(turn).getByRole('button', { name: 'Try again' }));
  await within(turn).findByText(/The question could not be answered/);
  expect(posts(api)).toHaveLength(2 * N);
});

it('CH-8 no askable drawing: the sentence, Ask disabled', async () => {
  const none: ProjectView = {
    ...project,
    drawings: project.drawings.map((d) => ({ ...d, state: 'set_aside' as const })),
  };
  open({}, none);
  expect(await screen.findByText('No drawing in this project can be asked yet.')).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' }).disabled).toBe(true);
});
