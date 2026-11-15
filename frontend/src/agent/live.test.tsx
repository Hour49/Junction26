// chat-ux #2: the pending row shows the agent's steps as the stream's events arrive (contract C).
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, info, project } from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { mockApi } from '../test/mockApi';
import { AgentChat } from './AgentChat';
import { answerTurn, model } from './fixtures';

const PID = project.id;
const enc = new TextEncoder();

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

/** /api/info of a server with the stream route (`chat.stream`), as the backend's fixture, and of one without. */
const streaming = {
  ...info,
  chat: { model: 'gemini', available: true, reason: null, stream: true },
};
const noStream = { ...info, chat: { ...streaming.chat, stream: false } };

/** The chat with the stream route held open: `push` sends one event, `fail` breaks the connection. */
async function open(server: unknown = streaming) {
  // one held-open stream per request; push and fail act on the newest
  let ctl!: ReadableStreamDefaultController<Uint8Array>;
  const api = mockApi({
    'GET /api/info': server,
    [`GET /api/projects/${PID}`]: project,
    [`POST /api/projects/${PID}/chat`]: answerTurn,
    ...Object.fromEntries<unknown>(
      project.drawings.flatMap((d) => [
        [`GET /api/drawings/${d.drawing_id}`, drawing],
        [`GET /api/drawings/${d.drawing_id}/model`, model],
      ]),
    ),
  });
  const stream = vi.fn<(init?: RequestInit) => Promise<Response>>(() => {
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        ctl = c;
      },
    });
    return Promise.resolve(
      new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
    );
  });
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) =>
    url.endsWith('/chat/stream') ? stream(init) : api.fetch(url, init),
  );
  render(
    <InfoProvider>
      <AgentChat projectId={PID} />
    </InfoProvider>,
  );
  // /api/info has answered before the first ask
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  const push = async (event: string, data: unknown) => {
    await act(async () => {
      ctl.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      await new Promise((r) => setTimeout(r, 0));
    });
  };
  const fail = async () => {
    await act(async () => {
      ctl.error(new TypeError('network error'));
      await new Promise((r) => setTimeout(r, 0));
    });
  };
  return { push, fail, stream, api };
}

async function send(message: string) {
  fireEvent.change(await screen.findByLabelText('Question'), { target: { value: message } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
}

const lines = () =>
  within(screen.getByRole('list', { name: 'What the agent is doing' }))
    .getAllByRole('listitem')
    .map((li) => li.textContent);

const call = { n: 1, tool: 'ask_drawings', label: 'Asked the drawings: How many doors?' };

it('each step shows as it is planned, runs and ends with its summary; then the answer replaces them', async () => {
  const { push } = await open();
  await send('How many doors?');
  expect(await screen.findByText('Working on it…')).toBeTruthy();
  await push('turn', { chat_id: 'c1', turn: 1 });
  await push('thinking', { step: 1 });
  expect(screen.getByText('Thinking…')).toBeTruthy();
  await push('plan', {
    step: 1,
    calls: [call, { n: 2, tool: 'list_drawings', label: 'Listed the drawings of the project' }],
  });
  expect(lines()).toEqual([
    'Asked the drawings: How many doors? (next)',
    'Listed the drawings of the project (next)',
  ]);
  await push('tool_call', call);
  expect(lines()[0]).toBe('Asked the drawings: How many doors? (running)');
  expect(screen.queryByText('Thinking…')).toBeNull();
  await push('tool_result', {
    ...call,
    status: 'ok',
    ms: 812,
    summary: 'Scanned plan 1: 19 doors (Low)',
  });
  expect(lines()[0]).toBe(
    '✓Asked the drawings: How many doors? (done)Scanned plan 1: 19 doors (Low)',
  );
  // the step after the tools: the model writes its reply (two steps per turn, chat-latency.md)
  await push('tool_result', {
    n: 2,
    tool: 'list_drawings',
    label: 'Listed the drawings of the project',
    status: 'ok',
    ms: 3,
    summary: null,
  });
  await push('thinking', { step: 2 });
  expect(screen.getByText('Writing the answer…')).toBeTruthy();
  expect(screen.queryByText('Thinking…')).toBeNull();
  await push('checking', {
    status: 'retry',
    reason: 'a number in the answer is not in the results',
  });
  expect(
    screen.getByText('Checking again: a number in the answer is not in the results'),
  ).toBeTruthy();
  await push('checking', { status: 'ok', reason: null });
  expect(screen.getByText('Checking the answer…')).toBeTruthy();
  await push('answer', answerTurn);
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(screen.queryByRole('list', { name: 'What the agent is doing' })).toBeNull();
  expect(screen.queryByRole('status')).toBeNull();
});

it('a connection lost mid-turn says so, keeps the chat id, and is not sent again by itself', async () => {
  const { push, fail, stream, api } = await open();
  await send('How many doors?');
  await push('turn', { chat_id: 'c1', turn: 1 });
  await push('tool_call', call);
  await fail();
  expect((await screen.findByRole('alert')).textContent).toMatch(/connection was lost/);
  expect(stream).toHaveBeenCalledTimes(1);
  expect(api.calls.filter((c) => c.method === 'POST')).toEqual([]); // no sync resend
  // Asking again continues the chat the server already started.
  await send('How many doors?');
  expect(stream).toHaveBeenCalledTimes(2);
  expect(JSON.parse(stream.mock.calls[1]?.[0]?.body as string)).toEqual({
    chat_id: 'c1',
    message: 'How many doors?',
  });
  await push('answer', answerTurn);
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
});

it('a server whose /api/info says chat.stream false gets the sync POST, never the stream route', async () => {
  const { stream, api } = await open(noStream);
  await send('How many doors?');
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(stream).not.toHaveBeenCalled();
  expect(api.calls.filter((c) => c.method === 'POST').map((c) => c.url)).toEqual([
    `/api/projects/${PID}/chat`,
  ]);
});
