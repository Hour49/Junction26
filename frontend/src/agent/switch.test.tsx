// CH-43: the project chat route picks the agent chat when GET /api/info says it is available, else the ask chat.
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { Info } from '../api';
import { drawing, info, project } from '../api/fixtures';
import { ProjectChat } from '../engineer/ProjectChat';
import { InfoProvider, useInfo } from '../shell/info';
import { mockApi, reply } from '../test/mockApi';
import { answerTurn } from './fixtures';

const PID = project.id;

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
});

/** In the app /api/info loads at start, before the user reaches the chat: mount it once info is known. */
function AfterInfo({ query }: { query?: string }) {
  const { info } = useInfo();
  return info && <ProjectChat projectId={PID} query={new URLSearchParams(query)} />;
}

function open(chat: Info['chat'], query?: string) {
  const api = mockApi({
    'GET /api/info': { ...info, chat },
    [`GET /api/projects/${PID}`]: project,
    ...Object.fromEntries(
      project.drawings.map((d) => [`GET /api/drawings/${d.drawing_id}`, drawing]),
    ),
    [`POST /api/projects/${PID}/chat`]: answerTurn,
    // no stream route: the sync POST (chat-ux #2)
    [`POST /api/projects/${PID}/chat/stream`]: reply(404, {
      detail: 'Not Found',
      code: 'not_found',
    }),
  });
  render(
    <InfoProvider>
      <AfterInfo query={query} />
    </InfoProvider>,
  );
  return api;
}

/** The ask chat after /api/info has answered: its box is there and no "Point at the plan". */
async function askChatStays(api: ReturnType<typeof mockApi>) {
  await waitFor(() => {
    expect(api.calls.some((c) => c.url === '/api/info')).toBe(true);
  });
  await screen.findByLabelText('Question');
  await new Promise((r) => setTimeout(r, 0));
  expect(screen.queryByRole('button', { name: 'Point at the plan' })).toBeNull();
}

it('CH-43 chat.available true: the agent chat', async () => {
  open({ model: 'rules', available: true, reason: null, stream: false });
  expect(await screen.findByRole('button', { name: 'Point at the plan' })).toBeTruthy();
});

it('CH-43 chat.available false or model off: the ask chat as before', async () => {
  await askChatStays(
    open({ model: 'gemini', available: false, reason: 'no GEMINI_API_KEY', stream: false }),
  );
  cleanup();
  await askChatStays(open({ model: 'off', available: false, reason: null, stream: false }));
  cleanup();
  await askChatStays(open(null));
});

it('CH-44 the agent chat sends ?ask= on open, once', async () => {
  const api = open(
    { model: 'rules', available: true, reason: null, stream: false },
    'ask=How+big+is+Bagno+1.01%3F',
  );
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  const posts = api.calls.filter((c) => c.method === 'POST' && c.url.endsWith('/chat'));
  expect(posts.map((c) => c.body)).toEqual([{ message: 'How big is Bagno 1.01?' }]);
});
