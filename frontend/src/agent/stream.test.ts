// chat-ux #2: the step stream client (.agents/chat/contract.md C): the SSE parser, the fallbacks to the sync route,
// and the live lines from the events.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { answerTurn } from './fixtures';
import { LIVE_START, liveStep, SseParser, streamTurn, type StreamEvent } from './stream';

const PID = 'p1';
const BODY = { message: 'How many doors?' };

/** contract.md C's fixture, as the server writes it. */
const FIXTURE = [
  'event: turn\ndata: {"chat_id":"3fa1c2d4e5f6","turn":1}\n\n',
  'event: thinking\ndata: {"step":1}\n\n',
  'event: plan\ndata: {"step":1,"calls":[{"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?"}]}\n\n',
  ': ping\n\n',
  'event: tool_call\ndata: {"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?"}\n\n',
  'event: tool_result\ndata: {"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?","status":"ok","ms":812.4,"summary":"Scanned plan 1: 19 doors (Low)"}\n\n',
  'event: thinking\ndata: {"step":2}\n\n',
  'event: checking\ndata: {"status":"ok","reason":null}\n\n',
  `event: answer\ndata: ${JSON.stringify(answerTurn)}\n\n`,
];

const enc = new TextEncoder();
/** A text/event-stream response of these chunks; `fail` makes the read fail after them. */
function sse(chunks: string[], fail = false): Response {
  let i = 0;
  // pull: one chunk per read, then the end (an error() in start would drop the queued chunks)
  const body = new ReadableStream<Uint8Array>({
    pull(c) {
      const k = chunks[i++];
      if (k !== undefined) c.enqueue(enc.encode(k));
      else if (fail) c.error(new TypeError('network error'));
      else c.close();
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** fetch answering the stream route with `stream` and the sync route with answerTurn; returns the URLs asked. */
function routes(stream: () => Response | Promise<Response>) {
  const urls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      urls.push(url);
      return Promise.resolve(url.endsWith('/chat/stream') ? stream() : json(200, answerTurn));
    }),
  );
  return urls;
}
const SYNC = `/api/projects/${PID}/chat`;
const STREAM = `${SYNC}/stream`;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SseParser', () => {
  it('cuts events across chunk edges, joins data lines, drops comments, reads CRLF', () => {
    const p = new SseParser();
    expect(p.feed('event: a\r\ndata: {"x"')).toEqual([]);
    expect(p.feed(':1}\r\n\r\n: ping\n\nevent: b\ndata: 1\ndata: 2\n\n')).toEqual([
      { event: 'a', data: '{"x":1}' },
      { event: 'b', data: '1\n2' },
    ]);
  });
});

describe('streamTurn', () => {
  it("calls onEvent for each of the contract's events in order and resolves with the answer's ChatTurn", async () => {
    const urls = routes(() => sse(FIXTURE.flatMap((k) => [k.slice(0, 7), k.slice(7)])));
    const seen: StreamEvent[] = [];
    const turn = await streamTurn(PID, BODY, (e) => seen.push(e));
    expect(turn).toEqual(answerTurn);
    expect(seen.map((e) => e.type)).toEqual([
      'turn',
      'thinking',
      'plan',
      'tool_call',
      'tool_result',
      'thinking',
      'checking',
      'answer',
    ]);
    expect(seen[0]).toEqual({ type: 'turn', chat_id: '3fa1c2d4e5f6', turn: 1 });
    expect(urls).toEqual([STREAM]);
  });

  it('sends the body as JSON and asks for an event stream', async () => {
    const f = vi.fn(() => Promise.resolve(sse(FIXTURE)));
    vi.stubGlobal('fetch', f);
    await streamTurn(PID, BODY, () => undefined);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(STREAM);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual(BODY);
    expect((init.headers as Record<string, string>).Accept).toBe('text/event-stream');
  });

  it.each([404, 405])(
    'a server without the stream route (%i) gets the sync POST',
    async (status) => {
      const urls = routes(() => json(status, { detail: 'Not Found', code: 'not_found' }));
      expect(await streamTurn(PID, BODY, () => undefined)).toEqual(answerTurn);
      expect(urls).toEqual([STREAM, SYNC]);
    },
  );

  it('a 200 that is not an event stream gets the sync POST', async () => {
    const urls = routes(() => json(200, answerTurn));
    expect(await streamTurn(PID, BODY, () => undefined)).toEqual(answerTurn);
    expect(urls).toEqual([STREAM, SYNC]);
  });

  it('a connection that fails before any event gets the sync POST', async () => {
    const urls = routes(() => Promise.reject(new TypeError('Failed to fetch')));
    expect(await streamTurn(PID, BODY, () => undefined)).toEqual(answerTurn);
    expect(urls).toEqual([STREAM, SYNC]);
    const urls2 = routes(() => sse([': ping\n\n'], true));
    expect(await streamTurn(PID, BODY, () => undefined)).toEqual(answerTurn);
    expect(urls2).toEqual([STREAM, SYNC]);
  });

  it('a connection lost after the turn started is an error and is never resent', async () => {
    const urls = routes(() => sse(FIXTURE.slice(0, 3), true));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status: 0,
      code: 'network',
    });
    const ended = routes(() => sse(FIXTURE.slice(0, 3)));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toBeInstanceOf(ApiError);
    expect(urls).toEqual([STREAM]);
    expect(ended).toEqual([STREAM]);
  });

  it("an error event fails the turn with the server's detail", async () => {
    routes(() =>
      sse([
        FIXTURE[0] as string,
        'event: error\ndata: {"status":500,"detail":"the model failed"}\n\n',
      ]),
    );
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status: 500,
      detail: 'the model failed',
    });
  });

  it('an HTTP error before the turn (409 a turn is still running) is that error, not a resend', async () => {
    const urls = routes(() => json(409, { detail: 'a turn is still running', code: 'busy' }));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status: 409,
      detail: 'a turn is still running',
    });
    expect(urls).toEqual([STREAM]);
  });
});

describe('liveStep', () => {
  const call = { n: 1, tool: 'ask_drawings', label: 'Asked the drawings: doors' };
  it('planned, running, then done with the summary; thinking and checking as what it does now', () => {
    let live = liveStep(LIVE_START, { type: 'thinking', step: 1 });
    expect(live.now).toEqual({ kind: 'thinking' });
    live = liveStep(live, {
      type: 'plan',
      step: 1,
      calls: [call, { ...call, n: 2, label: 'Read the plan' }],
    });
    expect(live.steps.map((s) => [s.n, s.status])).toEqual([
      [1, 'planned'],
      [2, 'planned'],
    ]);
    expect(live.now).toBeNull();
    live = liveStep(live, { type: 'tool_call', ...call });
    expect(live.steps[0]?.status).toBe('running');
    live = liveStep(live, {
      type: 'tool_result',
      ...call,
      status: 'ok',
      ms: 800,
      summary: '17 doors (Low)',
    });
    expect(live.steps[0]).toEqual({
      n: 1,
      label: call.label,
      status: 'ok',
      summary: '17 doors (Low)',
    });
    live = liveStep(live, {
      type: 'tool_result',
      ...call,
      n: 2,
      status: 'error',
      ms: 3,
      summary: null,
    });
    expect(live.steps[1]?.status).toBe('error');
    live = liveStep(live, {
      type: 'checking',
      status: 'retry',
      reason: 'a number is not in the results',
    });
    expect(live.now).toEqual({ kind: 'retry', reason: 'a number is not in the results' });
  });
});
