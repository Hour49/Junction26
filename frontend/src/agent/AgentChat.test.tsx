import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, fileReadAsPlan, project } from '../api/fixtures';
import { mockApi, never } from '../test/mockApi';
import { AgentChat } from './AgentChat';
import type { ChatRequest } from './agent';
import { answerTurn, dontKnowTurn, model, needsInputTurn } from './fixtures';

const PID = project.id;
const CHAT = `POST /api/projects/${PID}/chat`;
const drawings: Record<string, unknown> = Object.fromEntries<unknown>(
  project.drawings.flatMap((d) => [
    [`GET /api/drawings/${d.drawing_id}`, drawing],
    [`GET /api/drawings/${d.drawing_id}/model`, model],
  ]),
);

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear(); // the kept thread (answers-5)
});

function open(chat: unknown, query?: string) {
  const api = mockApi({ [`GET /api/projects/${PID}`]: project, ...drawings, [CHAT]: chat });
  render(<AgentChat projectId={PID} query={new URLSearchParams(query)} />);
  return api;
}

async function send(message: string) {
  const input = await screen.findByLabelText('Question');
  fireEvent.change(input, { target: { value: message } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
}

const posts = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.method === 'POST').map((c) => c.body as ChatRequest);

it('AC-30 first turn without chat_id, the next with the returned one; one turn pending at a time', async () => {
  let n = 0;
  const api = open(() => (n++ === 0 ? needsInputTurn : answerTurn));
  await send('Make the bathroom larger');
  expect(await screen.findByText('There are two bathrooms. Which one do you mean?')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Bagno 1.01' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(posts(api)).toEqual([
    { message: 'Make the bathroom larger' },
    {
      chat_id: needsInputTurn.chat_id,
      message: 'Remove the wall between Bagno 1.01 and the bedroom',
    },
  ]);
});

it('AC-30 while a turn is pending the ask button is disabled', async () => {
  open(never());
  await send('How big is the bathroom?');
  expect(await screen.findByText('Working on it…')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Ask' })).toHaveProperty('disabled', true);
});

it('AC-30 a failed turn says why and can be sent again', async () => {
  let n = 0;
  open(() =>
    n++ === 0 ? { status: 500, body: { detail: 'internal error', code: 'internal' } } : answerTurn,
  );
  await send('How big is the bathroom?');
  expect((await screen.findByRole('alert')).textContent).toMatch(/internal error/);
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
});

/** Opens the pointer on Drawn plan 1 and returns the page stage, sized 600 × 400 px. */
async function pointer() {
  fireEvent.click(await screen.findByRole('button', { name: 'Point at the plan' }));
  fireEvent.click(screen.getByRole('button', { name: 'Drawn plan 1' }));
  const frame = await waitFor(() => {
    const f = document.querySelector('.vw-frame');
    if (!f) throw new Error('no page yet');
    return f as HTMLElement;
  });
  frame.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 600, height: 400, right: 600, bottom: 400, x: 0, y: 0 }) as DOMRect;
  return frame.parentElement as HTMLElement;
}

it('AC-33 Point at the plan: a dragged area goes with the next message as a chip, then is cleared', async () => {
  const api = open(answerTurn);
  const stage = await pointer();
  fireEvent.pointerDown(stage, { clientX: 60, clientY: 40, pointerType: 'mouse', button: 0 });
  fireEvent.pointerUp(stage, { clientX: 240, clientY: 120, pointerType: 'mouse', button: 0 });
  expect(await screen.findByText('Area on Drawn plan 1, page 1')).toBeTruthy();
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  const [body] = posts(api);
  expect(body?.selection).toEqual([
    {
      id: 'sel_1',
      kind: 'region',
      drawing_id: project.drawings[0]?.drawing_id,
      page: 1,
      box: expect.any(Array) as unknown,
    },
  ]);
  expect(screen.queryByRole('button', { name: 'Remove Area on Drawn plan 1, page 1' })).toBeNull();
});

it('AC-33 a click on a room sends its model id and the chip names it', async () => {
  const api = open(answerTurn);
  const stage = await pointer();
  fireEvent.pointerDown(stage, { clientX: 120, clientY: 80, pointerType: 'mouse', button: 0 });
  fireEvent.pointerUp(stage, { clientX: 120, clientY: 80, pointerType: 'mouse', button: 0 });
  expect(await screen.findByText('Room Bagno 1.01')).toBeTruthy();
  await send('Make this room larger');
  await screen.findByText(/is 7.56 m²/);
  expect(posts(api)[0]?.selection).toEqual([
    expect.objectContaining({ id: 'sel_1', kind: 'room', ref: 'R3', page: 1 }),
  ]);
});

it('CH-45 follow-up chips after an answer (questions not asked yet); none after a dont_know', async () => {
  let n = 0;
  open(() => (n++ === 0 ? answerTurn : dontKnowTurn));
  await send('How many doors are there?');
  await screen.findByText(/is 7.56 m²/);
  const next = screen.getByRole('group', { name: 'Follow-up questions' });
  expect(next.textContent).not.toContain('How many doors are there?');
  expect(next.textContent).toContain('How many windows are there?');
  await send('Is that wall load-bearing?');
  await screen.findByText("I don't know.");
  expect(screen.queryByRole('group', { name: 'Follow-up questions' })).toBeNull();
});

it("LC-11 every turn sends the route's ?pack=; none without one", async () => {
  const api = open(answerTurn, 'pack=ch-zh');
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  await send('And now?');
  await waitFor(() => {
    expect(posts(api)).toHaveLength(2);
  });
  expect(posts(api).map((b) => b.pack)).toEqual(['ch-zh', 'ch-zh']);
  cleanup();
  sessionStorage.clear(); // a new chat, not the kept one
  const bare = open(answerTurn);
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  expect(posts(bare)[0]).not.toHaveProperty('pack');
});

it('CH-18 agent chat: a photo read as a plan makes a project with no askable drawing askable', async () => {
  const added = { ...fileReadAsPlan, id: 'f9', path: 'plan.jpg', state: 'queued' as const };
  const before = { ...project, drawings: [] };
  const after = { ...project, files: [...project.files, { ...added, state: 'ready' as const }] };
  let n = 0;
  const api = mockApi({
    [`GET /api/projects/${PID}`]: () => (n++ === 0 ? before : after),
    ...drawings,
    [`POST /api/projects/${PID}/files`]: added,
    [CHAT]: answerTurn,
  });
  render(<AgentChat projectId={PID} />);
  expect(await screen.findByText('No drawing in this project can be asked yet.')).toBeTruthy();
  fireEvent.change(screen.getByTestId('photo-input'), {
    target: { files: [new File(['jpeg'], 'plan.jpg', { type: 'image/jpeg' })] },
  });
  expect(await screen.findByText('Reading plan.jpg…')).toBeTruthy();
  expect(
    await screen.findByText(/^plan\.jpg is read: you can ask about it \(/, {}, { timeout: 4000 }),
  ).toBeTruthy();
  expect(screen.queryByText('No drawing in this project can be asked yet.')).toBeNull();
  const post = api.calls.find((c) => c.url.startsWith(`/api/projects/${PID}/files`));
  expect(post?.url).toBe(`/api/projects/${PID}/files?name=plan.jpg`);
  await send('How many doors are there?');
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
}, 8000);
