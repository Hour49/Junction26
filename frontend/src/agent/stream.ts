// The agent's live steps (.agents/chat/contract.md C): Server-Sent Events over a POST, read with fetch, and what the
// pending row shows from them. Every line shown is server-written (labels, summaries, reasons); nothing is invented.
import { ApiError, errorOf } from '../api';
import type { ChatRequest, ChatTurn, Step, View } from './agent';

type Call = { n: number; tool: string; label: string };

/** One event of the stream, by its `event:` type, with its `data` JSON. */
export type StreamEvent =
  | { type: 'turn'; chat_id: string; turn: number }
  | { type: 'thinking'; step: number }
  | { type: 'plan'; step: number; calls: Call[] }
  | ({ type: 'tool_call' } & Call)
  | ({ type: 'tool_result' } & Step & { summary: string | null })
  | { type: 'view'; view: View }
  | { type: 'checking'; status: 'ok' | 'retry'; reason: string | null }
  | { type: 'answer'; turn: ChatTurn }
  | { type: 'error'; status: number; detail: string };

/** Cuts a text/event-stream into `{event, data}` messages as chunks arrive; `: ping` comments are dropped. */
export class SseParser {
  private buffer = '';

  feed(chunk: string): { event: string; data: string }[] {
    this.buffer += chunk.replace(/\r\n?/g, '\n');
    const out: { event: string; data: string }[] = [];
    let end = this.buffer.indexOf('\n\n');
    while (end >= 0) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      let event = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith(':')) continue;
        const colon = line.indexOf(':');
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
        if (field === 'event') event = value;
        else if (field === 'data') data.push(value);
      }
      if (data.length) out.push({ event, data: data.join('\n') });
      end = this.buffer.indexOf('\n\n');
    }
    return out;
  }
}

/** A message as a typed event: `answer` carries the ChatTurn as its data, `view` the View (contract A). */
function eventOf(m: { event: string; data: string }): StreamEvent {
  const data = JSON.parse(m.data) as Record<string, unknown>;
  if (m.event === 'answer') return { type: 'answer', turn: data as unknown as ChatTurn };
  if (m.event === 'view') return { type: 'view', view: data as unknown as View };
  return { ...data, type: m.event } as StreamEvent;
}

const LOST = 'The connection was lost while the agent was working. Ask again.';

/** A live stream sends a byte at least every 10 s (the server's ping, contract C); this long with none, the
 * connection is gone even if it was never closed (a killed backend behind a proxy, a frozen one), so the turn fails
 * as lost instead of spinning forever (QA R2-C6). */
export const STREAM_IDLE_MS = 45_000;

/** `step`, or a lost connection (after `onLost`) when it has not settled in STREAM_IDLE_MS. */
async function orLost<T>(step: Promise<T>, onLost: () => void): Promise<T> {
  let idle: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      step,
      new Promise<never>((_, reject) => {
        idle = setTimeout(() => {
          reject(new ApiError(0, 'network', LOST)); // first: the abort onLost makes must not win the race
          onLost();
        }, STREAM_IDLE_MS);
      }),
    ]);
  } finally {
    clearTimeout(idle);
  }
}

/** One turn over the stream route, calling `onEvent` for each event; resolves with the final ChatTurn. Only for a
 * server whose /api/info says `chat.stream` (the caller picks the sync route otherwise). Never resends: a lost
 * connection may have started the turn on the server. */
export async function streamTurn(
  projectId: string,
  body: ChatRequest,
  onEvent: (e: StreamEvent) => void,
  opts: { signal?: AbortSignal } = {},
): Promise<ChatTurn> {
  let response: Response;
  const stop = new AbortController(); // frees a request that never answered
  try {
    response = await orLost(
      fetch(`/api/projects/${encodeURIComponent(projectId)}/chat/stream`, {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        signal: opts.signal ? AbortSignal.any([opts.signal, stop.signal]) : stop.signal,
      }),
      () => {
        stop.abort();
      },
    );
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as { name?: unknown } | null)?.name === 'AbortError') throw error;
    throw new ApiError(0, 'network', 'cannot reach the server');
  }
  if (!response.ok) throw await errorOf(response);
  const reader = response.body?.getReader();
  if (!reader) throw new ApiError(0, 'network', LOST);
  const parser = new SseParser();
  const decoder = new TextDecoder();
  for (;;) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await orLost(reader.read(), () => {
        void reader.cancel().catch(() => undefined);
      });
    } catch (error) {
      if ((error as { name?: unknown } | null)?.name === 'AbortError') throw error;
      throw new ApiError(0, 'network', LOST);
    }
    const text = chunk.done ? decoder.decode() : decoder.decode(chunk.value, { stream: true });
    for (const m of parser.feed(chunk.done ? `${text}\n\n` : text)) {
      const e = eventOf(m);
      onEvent(e);
      if (e.type === 'answer') {
        void reader.cancel();
        return e.turn;
      }
      if (e.type === 'error') {
        void reader.cancel();
        throw new ApiError(e.status, 'stream', e.detail);
      }
    }
    if (chunk.done) throw new ApiError(0, 'network', LOST);
  }
}

/** A tool line of the live steps: planned (the model chose it), running, then ok or error with the server's
 * one-line summary of what it found. */
export type LiveStep = {
  n: number;
  label: string;
  status: 'planned' | 'running' | 'ok' | 'error';
  summary: string | null;
};
/** What the pending row shows: the tool lines, and what the agent is doing now. */
export type Live = {
  steps: LiveStep[];
  now:
    | { kind: 'thinking' }
    | { kind: 'writing' }
    | { kind: 'checking' }
    | { kind: 'retry'; reason: string | null }
    | null;
};

export const LIVE_START: Live = { steps: [], now: null };

function put(steps: LiveStep[], s: LiveStep): LiveStep[] {
  const i = steps.findIndex((x) => x.n === s.n);
  if (i < 0) return [...steps, s].sort((a, b) => a.n - b.n);
  return steps.map((x, j) => (j === i ? s : x));
}

/** The live state after one event (pure). */
export function liveStep(live: Live, e: StreamEvent): Live {
  switch (e.type) {
    case 'thinking':
      // A model step once every tool line has ended reads their results: most often it writes the reply
      // (.agents/exp/chat-latency.md), about 1 in 5 it picks more tools (review-481), whose plan replaces this.
      return {
        ...live,
        now:
          live.steps.length > 0 &&
          live.steps.every((x) => x.status === 'ok' || x.status === 'error')
            ? { kind: 'writing' }
            : { kind: 'thinking' },
      };
    case 'plan':
      return {
        steps: e.calls.reduce(
          (steps, c) =>
            steps.some((x) => x.n === c.n)
              ? steps
              : put(steps, { n: c.n, label: c.label, status: 'planned', summary: null }),
          live.steps,
        ),
        now: null,
      };
    case 'tool_call':
      return {
        steps: put(live.steps, { n: e.n, label: e.label, status: 'running', summary: null }),
        now: null,
      };
    case 'tool_result':
      return {
        steps: put(live.steps, {
          n: e.n,
          label: e.label,
          status: e.status === 'error' ? 'error' : 'ok',
          summary: e.summary,
        }),
        now: null,
      };
    case 'checking':
      return {
        ...live,
        now: e.status === 'retry' ? { kind: 'retry', reason: e.reason } : { kind: 'checking' },
      };
    default:
      return live;
  }
}
