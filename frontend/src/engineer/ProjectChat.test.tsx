import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { ProjectAnswer, ProjectView } from '../api';
import {
  answerArea,
  answerRefused,
  drawing,
  error,
  fileReadAsPlan,
  project,
  projectAsk,
} from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import { AskBox } from './AskBox';
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
  query?: string,
  strict = false,
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
  const chat = (
    <ProjectChat
      projectId={PID}
      query={query === undefined ? undefined : new URLSearchParams(query)}
    />
  );
  render(strict ? <StrictMode>{chat}</StrictMode> : chat);
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
  expect(show.getAttribute('href')).toMatch(`#/p/${PID}/d/${flatA.drawing_id}/engineer?ask=`);
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

it('CH-14 ?ask= asks the project once on open (also in StrictMode): the thread, no start page', async () => {
  const q = 'How many doors are there?';
  const api = open(
    projectAsk,
    project,
    drawingRoutes(),
    new URLSearchParams({ ask: q }).toString(),
    true,
  );
  await waitFor(() => {
    expect(screen.getByRole('article', { name: q }).querySelector('.en-chatcard')).toBeTruthy();
  });
  expect(posts(api).map((c) => c.body)).toEqual([{ question: q }]);
  expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
  expect(document.querySelector('.en-chat--empty')).toBeNull();
});

it('CH-15 nothing asked for an empty ?ask=, a project 404, or no askable drawing', async () => {
  const api = open(noneAnswers, project, drawingRoutes(), 'ask=%20');
  await screen.findByRole('group', { name: 'Suggested questions' });
  expect(document.querySelector('.en-chat--empty')).toBeTruthy();
  cleanup();
  const failed = open(noneAnswers, { status: 404, body: error }, drawingRoutes(), 'ask=doors');
  await screen.findByRole('link', { name: 'Back to the project' });
  cleanup();
  const none: ProjectView = {
    ...project,
    drawings: project.drawings.map((d) => ({ ...d, state: 'set_aside' as const })),
  };
  const empty = open(noneAnswers, none, drawingRoutes(), 'ask=doors');
  await screen.findByText('No drawing in this project can be asked yet.');
  expect([...posts(api), ...posts(failed), ...posts(empty)]).toEqual([]);
});

it('CH-16 Show it on <name> opens that drawing asking this question; ?pack= is kept (QA R4b-1)', async () => {
  const q = 'How many doors are there?';
  const href = (name: string) =>
    within(line(screen.getByRole('article', { name: q }), name))
      .getByRole('link', { name: `Show it on ${name}` })
      .getAttribute('href') ?? '';
  open(projectAsk);
  await answered(q);
  expect(href(flatA.name)).toBe(
    `#/p/${PID}/d/${flatA.drawing_id}/engineer?${new URLSearchParams({ ask: q }).toString()}`,
  );
  cleanup();
  open(projectAsk, project, drawingRoutes(), 'pack=fi');
  await answered(q);
  const query = new URLSearchParams(href(flatB.name).split('?')[1]);
  expect([query.get('ask'), query.get('pack')]).toEqual([q, 'fi']);
});

// Adding a photo (board #203): the new file f4, its drawing askable once read.
const ADD = `POST /api/projects/${PID}/files`;
const PHOTO = 'plan.jpg';
const added = { ...fileReadAsPlan, id: 'f4', path: PHOTO, state: 'queued' as const };
const photoDrawing = {
  ...(project.drawings[0] as ProjectView['drawings'][number]),
  drawing_id: 'photo0001',
  file: PHOTO,
  state: 'ready' as const,
};
/** The project after the photo: f4 in `state`, and its drawing when it was read as a plan. */
const withPhoto = (state: 'running' | 'ready' | 'set_aside'): ProjectView => ({
  ...project,
  files: [...project.files, { ...added, state, reason: 'not a plan: a photo of a cat.' }],
  drawings: state === 'ready' ? [...project.drawings, photoDrawing] : project.drawings,
});
/** The project route answers `project` first, then each of `polls` in turn (the last repeats). */
function openWithPhoto(addReply: unknown, polls: ProjectView[]) {
  let n = 0;
  return mockApi({
    [ROUTE]: () => (n++ === 0 ? project : polls[Math.min(n - 2, polls.length - 1)]),
    ...drawingRoutes(),
    [`GET /api/drawings/photo0001`]: drawing,
    [ADD]: addReply,
    [ASK]: (c: { body: unknown }) => ({
      ...noneAnswers,
      question: (c.body as { question: string }).question,
    }),
  });
}
async function pick() {
  render(<ProjectChat projectId={PID} />);
  await screen.findByRole('heading', { level: 1, name: project.name });
  const input = screen.getByTestId<HTMLInputElement>('photo-input');
  fireEvent.change(input, {
    target: { files: [new File(['jpeg'], PHOTO, { type: 'image/jpeg' })] },
  });
}
const slow = { timeout: 4000 };

it('CH-17 the chat has "Add a photo" for png and jpeg; the ask bar without onAttach has none', async () => {
  openWithPhoto(added, [withPhoto('ready')]);
  render(<ProjectChat projectId={PID} />);
  expect(await screen.findByRole('button', { name: 'Add a photo' })).toBeTruthy();
  expect(screen.getByTestId('photo-input').getAttribute('accept')).toBe('image/png,image/jpeg');
  cleanup();
  render(<AskBox file="x" busy={false} asked={0} onAsk={() => undefined} />);
  expect(screen.queryByRole('button', { name: 'Add a photo' })).toBeNull();
});

it('CH-18 a picked photo is posted, read while polled, then askable', async () => {
  const api = openWithPhoto(added, [withPhoto('running'), withPhoto('ready')]);
  await pick();
  expect(await screen.findByText(`Reading ${PHOTO}…`)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Add a photo' }).disabled).toBe(
    true,
  );
  const post = api.calls.find((c) => c.url.startsWith(`/api/projects/${PID}/files`));
  expect(post?.url).toBe(`/api/projects/${PID}/files?name=${PHOTO}`);
  expect(post?.body).toBeInstanceOf(File);
  expect(await screen.findByText(`${PHOTO} is read: you can ask about it.`, {}, slow)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Add a photo' }).disabled).toBe(
    false,
  );
  await ask('How many doors are there?');
  expect(posts(api).filter((c) => c.url.endsWith('/ask'))).toHaveLength(1);
}, 8000);

it('CH-19 a photo that is not a plan says why', async () => {
  openWithPhoto(added, [withPhoto('set_aside')]);
  await pick();
  expect(
    await screen.findByText(
      `${PHOTO} was not read as a plan: not a plan: a photo of a cat.`,
      {},
      slow,
    ),
  ).toBeTruthy();
});

it('CH-20 a refused post says so, polls nothing and frees the paperclip', async () => {
  const api = openWithPhoto(reply(415, { detail: 'only png or jpeg', code: 'unsupported' }), [
    project,
  ]);
  await pick();
  expect(await screen.findByText(`Could not add ${PHOTO}: only png or jpeg`)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Add a photo' }).disabled).toBe(
    false,
  );
  await new Promise((r) => setTimeout(r, 1200));
  expect(
    api.calls.filter((c) => c.method === 'GET' && c.url === `/api/projects/${PID}`),
  ).toHaveLength(1);
});
