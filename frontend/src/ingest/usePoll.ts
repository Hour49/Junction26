import { useCallback, useEffect, useState } from 'react';

export const POLL_MS = 500;

/**
 * Load once, then again POLL_MS after each answer while `again(data)` holds (docs/API.md: poll every 500 ms
 * while queued or running). A failed request pauses polling until `retry`; the last data stays.
 * Unmount aborts the request in flight and cancels the next one.
 */
export function usePoll<T>(
  load: (signal: AbortSignal) => Promise<T>,
  again: (data: T) => boolean,
): {
  data: T | null;
  /** Browser time (ms) the data arrived: the clock a screen shows "now" by. */
  at: number;
  error: unknown;
  failedAt: string | null;
  retry: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [at, setAt] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [failedAt, setFailedAt] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const next = await load(controller.signal);
        if (controller.signal.aborted) return;
        setData(next);
        setAt(Date.now());
        setError(null);
        if (again(next))
          timer = setTimeout(() => {
            void tick();
          }, POLL_MS);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(e);
        setFailedAt(new Date().toISOString());
      }
    };
    void tick();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [load, again, attempt]);

  const retry = useCallback(() => {
    setAttempt((a) => a + 1);
  }, []);
  return { data, at, error, failedAt, retry };
}
