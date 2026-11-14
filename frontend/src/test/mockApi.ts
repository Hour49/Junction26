// A fetch stub for tests: routes keyed "<METHOD> <path>" (no query) answer with a fixture body.
import { onTestFinished, vi } from 'vitest';

export interface Call {
  method: string;
  url: string;
  /** The parsed JSON body, or the raw body (a File on upload), or undefined. */
  body: unknown;
}

/** A status other than the default, or an error body (a string body is sent as is, e.g. HTML). */
export interface Reply {
  status: number;
  body: unknown;
}

/** A JSON body, a `Reply`, a promise of either (`never()`), or a function of the call returning one. */
export type Route = unknown;

const CREATED = new Set(['POST /api/projects', 'POST /api/projects/sample']);

export function reply(status: number, body: unknown): Reply {
  return { status, body };
}

function isReply(value: unknown): value is Reply {
  if (typeof value !== 'object' || value === null) return false;
  const keys = Object.keys(value);
  return keys.length === 2 && typeof (value as Reply).status === 'number' && keys.includes('body');
}

/** A response that never comes: for loading states. */
export function never(): Promise<never> {
  return new Promise<never>(() => undefined);
}

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  return input instanceof URL ? input.href : input.url;
}

/** Stubs `fetch` for this test; a request no route matches fails the test when it ends. */
export function mockApi(routes: Record<string, Route>) {
  const calls: Call[] = [];
  const unmatched: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = urlOf(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const key = `${method} ${url.split('?')[0] ?? url}`;
    let body: unknown = init?.body ?? undefined;
    if (typeof body === 'string') {
      try {
        body = JSON.parse(body);
      } catch {
        // not JSON: keep the raw string
      }
    }
    const call: Call = { method, url, body };
    calls.push(call);
    if (!(key in routes)) {
      unmatched.push(key);
      return new Response(JSON.stringify({ detail: `mockApi: no route ${key}`, code: 'mock' }), {
        status: 599,
      });
    }
    const route = routes[key];
    const pending = typeof route === 'function' ? (route as (c: Call) => unknown)(call) : route;
    const signal = init?.signal;
    const answer = await new Promise<unknown>((resolve, reject) => {
      signal?.addEventListener('abort', () => {
        reject(new DOMException('aborted', 'AbortError'));
      });
      if (signal?.aborted) reject(new DOMException('aborted', 'AbortError'));
      Promise.resolve(pending).then(resolve, reject);
    });
    const { status, body: out } = isReply(answer)
      ? answer
      : { status: CREATED.has(key) ? 202 : 200, body: answer };
    const text = typeof out === 'string' ? out : JSON.stringify(out);
    return new Response(text, { status, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  onTestFinished(() => {
    vi.unstubAllGlobals();
    if (unmatched.length)
      throw new Error(`mockApi: unexpected request(s): ${unmatched.join(', ')}`);
  });
  return { calls, fetch: fetchMock };
}
