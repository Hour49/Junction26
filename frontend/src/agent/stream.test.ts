// chat-ux #2: the step stream client (.agents/chat/contract.md C): the SSE parser, its errors (never a resend), and
// the live lines from the events.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { answerTurn } from './fixtures';
import {
  LIVE_START,
  liveStep,
  SseParser,
  STREAM_IDLE_MS,
  streamTurn,
  type StreamEvent,
} from './stream';

const PID = 'p1';
const BODY = { message: 'How many doors?' };

/** show_on_plan's view (contract A), as the server sends it mid-turn. */
const VIEW = {
  drawing_id: 'd1',
  name: 'Plan 1',
  page: 1,
  box: [0.1, 0.1, 0.3, 0.3],
  marks: [{ n: 1, label: 'Kitchen', box: [0.12, 0.12, 0.28, 0.28], polygon: null }],
  caption: 'The kitchen',
  source: 'show_on_plan',
};

/** contract.md C's fixture, as the server writes it. */
const FIXTURE = [
  'event: turn\ndata: {"chat_id":"3fa1c2d4e5f6","turn":1}\n\n',
  'event: thinking\ndata: {"step":1}\n\n',
  'event: plan\ndata: {"step":1,"calls":[{"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?"}]}\n\n',
  ': ping\n\n',
  'event: tool_call\ndata: {"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?"}\n\n',
  'event: tool_result\ndata: {"n":1,"tool":"ask_drawings","label":"Asked the drawings: How many doors?","status":"ok","ms":812.4,"summary":"Scanned plan 1: 19 doors (Low)"}\n\n',
  `event: view\ndata: ${JSON.stringify(VIEW)}\n\n`,
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
/** One chunk per read, each `gapMs` after the last; then the stream stays open and silent (the backend killed
 * behind a proxy that keeps the connection, or frozen mid-turn). */
function slow(chunks: string[], gapMs: number): Response {
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(c) {
      const k = chunks[i++];
      if (k === undefined) return new Promise<void>(() => undefined);
      if (gapMs === 0) {
        c.enqueue(enc.encode(k));
        return undefined;
      }
      return new Promise<void>((done) => {
        setTimeout(() => {
          c.enqueue(enc.encode(k));
          done();
        }, gapMs);
      });
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
      'view',
      'thinking',
      'checking',
      'answer',
    ]);
    expect(seen[0]).toEqual({ type: 'turn', chat_id: '3fa1c2d4e5f6', turn: 1 });
    expect(seen[5]).toEqual({ type: 'view', view: VIEW });
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

  it('a connection that fails before any event is a network error, never resent to the sync route', async () => {
    const urls = routes(() => Promise.reject(new TypeError('Failed to fetch')));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status: 0,
      code: 'network',
    });
    const urls2 = routes(() => sse([': ping\n\n'], true));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status: 0,
      code: 'network',
    });
    expect(urls).toEqual([STREAM]);
    expect(urls2).toEqual([STREAM]);
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

  it('a stream silent for STREAM_IDLE_MS (no byte, no ping) is a lost connection, not a spinner forever (R2-C6)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }); // the stream's own scheduling stays real
    try {
      routes(() => slow(FIXTURE.slice(0, 3), 0));
      const failed = expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
        status: 0,
        code: 'network',
      });
      // in steps: each read's idle clock starts only after the last chunk went through the stream
      for (let t = 0; t < STREAM_IDLE_MS + 5_000; t += 5_000)
        await vi.advanceTimersByTimeAsync(5_000);
      await failed;
    } finally {
      vi.useRealTimers();
    }
  });

  it('a request with no answer at all for STREAM_IDLE_MS is a lost connection, and is aborted (R2-C6)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    try {
      let signal: AbortSignal | null | undefined;
      vi.stubGlobal(
        'fetch',
        vi.fn((_url: string, init: RequestInit) => {
          signal = init.signal;
          // as a browser's fetch: an abort rejects it at once
          return new Promise<Response>((_, reject) => {
            init.signal?.addEventListener('abort', () => {
              reject(new DOMException('signal is aborted without reason', 'AbortError'));
            });
          });
        }),
      );
      const failed = expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
        status: 0,
        code: 'network',
      });
      await vi.advanceTimersByTimeAsync(STREAM_IDLE_MS);
      await failed;
      expect(signal?.aborted).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("the server's pings keep a long turn alive: 80 s with a byte every 10 s still answers", async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    try {
      const pings = Array<string>(6).fill(': ping\n\n');
      routes(() => slow([FIXTURE[0] as string, ...pings, FIXTURE.at(-1) as string], 10_000));
      const turn = streamTurn(PID, BODY, () => undefined);
      for (let t = 0; t < 80_000; t += 1_000) await vi.advanceTimersByTimeAsync(1_000);
      await expect(turn).resolves.toEqual(answerTurn);
    } finally {
      vi.useRealTimers();
    }
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

  it.each([
    [409, 'a turn is still running'],
    [404, 'project p1 not found'],
  ])('an HTTP error before the turn (%i) is that error, not a resend', async (status, detail) => {
    const urls = routes(() => json(status, { detail, code: 'x' }));
    await expect(streamTurn(PID, BODY, () => undefined)).rejects.toMatchObject({
      status,
      detail,
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

  it('the model step after every tool line ended reads their results: "writing"', () => {
    const done = {
      type: 'tool_result' as const,
      ...call,
      status: 'ok' as const,
      ms: 800,
      summary: null,
    };
    let live = liveStep(LIVE_START, { type: 'thinking', step: 1 });
    expect(live.now).toEqual({ kind: 'thinking' }); // no tool has run: it is choosing its tools
    live = liveStep(live, { type: 'plan', step: 1, calls: [call, { ...call, n: 2 }] });
    live = liveStep(live, done);
    // one line still to run: the next model step has not started, and a "thinking" now would be another step
    expect(liveStep(live, { type: 'thinking', step: 2 }).now).toEqual({ kind: 'thinking' });
    live = liveStep(live, { ...done, n: 2, status: 'error' });
    live = liveStep(live, { type: 'thinking', step: 2 });
    expect(live.now).toEqual({ kind: 'writing' });
    // it chose more tools after all: their lines replace the writing state
    live = liveStep(live, { type: 'plan', step: 2, calls: [{ ...call, n: 3 }] });
    expect(live.now).toBeNull();
  });
});
