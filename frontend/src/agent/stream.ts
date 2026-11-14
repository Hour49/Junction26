// The agent's live steps (.agents/chat/contract.md C): Server-Sent Events over a POST, read with fetch, and what the
// pending row shows from them. Every line shown is server-written (labels, summaries, reasons); nothing is invented.
import { ApiError, chatTurn, errorOf } from '../api';
import type { ChatRequest, ChatTurn, Step } from './agent';

type Call = { n: number; tool: string; label: string };

/** One event of the stream, by its `event:` type, with its `data` JSON. */
export type StreamEvent =
  | { type: 'turn'; chat_id: string; turn: number }
  | { type: 'thinking'; step: number }
  | { type: 'plan'; step: number; calls: Call[] }
  | ({ type: 'tool_call' } & Call)
  | ({ type: 'tool_result' } & Step & { summary: string | null })
  | { type: 'view'; [key: string]: unknown }
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

/** A message as a typed event: `answer` carries the ChatTurn as its data. */
function eventOf(m: { event: string; data: string }): StreamEvent {
  const data = JSON.parse(m.data) as Record<string, unknown>;
  if (m.event === 'answer') return { type: 'answer', turn: data as unknown as ChatTurn };
  return { ...data, type: m.event } as StreamEvent;
}

const LOST = 'The connection was lost while the agent was working. Ask again.';

/** One turn over the stream route, calling `onEvent` for each event; resolves with the final ChatTurn. Falls back
 * to the sync route when the stream route is missing (404/405, or a 200 that is not a stream) or the connection
 * fails before any event. Once an event has come, never resends: the turn is running on the server. */
export async function streamTurn(
  projectId: string,
  body: ChatRequest,
  onEvent: (e: StreamEvent) => void,
  opts: { signal?: AbortSignal } = {},
): Promise<ChatTurn> {
  const sync = () => chatTurn(projectId, body, opts);
  let response: Response;
  try {
    response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/chat/stream`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      signal: opts.signal ?? null,
    });
  } catch (error) {
    if ((error as { name?: unknown } | null)?.name === 'AbortError') throw error;
    return sync();
  }
  if (response.status === 404 || response.status === 405) return sync();
  if (!response.ok) throw await errorOf(response);
  const reader = response.body?.getReader();
  if (!reader || !response.headers.get('Content-Type')?.includes('text/event-stream')) {
    await reader?.cancel();
    return sync();
  }
  const parser = new SseParser();
  const decoder = new TextDecoder();
  let seen = false;
  for (;;) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await reader.read();
    } catch (error) {
      if ((error as { name?: unknown } | null)?.name === 'AbortError') throw error;
      if (!seen) return sync();
      throw new ApiError(0, 'network', LOST);
    }
    const text = chunk.done ? decoder.decode() : decoder.decode(chunk.value, { stream: true });
    for (const m of parser.feed(chunk.done ? `${text}\n\n` : text)) {
      const e = eventOf(m);
      seen = true;
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
    if (chunk.done) {
      if (!seen) return sync();
      throw new ApiError(0, 'network', LOST);
    }
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
    { kind: 'thinking' } | { kind: 'checking' } | { kind: 'retry'; reason: string | null } | null;
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
      return { ...live, now: { kind: 'thinking' } };
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
