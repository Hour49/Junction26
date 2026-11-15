import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { getInfo, type Info } from '../api';

export interface InfoState {
  /** null until `GET /api/info` has answered. */
  info: Info | null;
  error: unknown;
  reload: () => void;
}

const InfoContext = createContext<InfoState>({ info: null, error: null, reload: () => undefined });

/** After a failed `GET /api/info`, it is asked again this often until it answers (a backend back from a freeze or
 * restart clears the error strip and brings the upload limits without a click). */
export const INFO_RETRY_MS = 15_000;

/** Asks `GET /api/info` once when the app starts, again on `reload`, and every INFO_RETRY_MS while it fails. */
export function InfoProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    let again: ReturnType<typeof setTimeout> | undefined;
    getInfo({ signal: abort.signal }).then(
      (found) => {
        setInfo(found);
        setError(null);
      },
      (failed: unknown) => {
        if (abort.signal.aborted) return;
        setError(failed);
        again = setTimeout(() => {
          setAttempt((n) => n + 1);
        }, INFO_RETRY_MS);
      },
    );
    return () => {
      abort.abort();
      clearTimeout(again);
    };
  }, [attempt]);
  const reload = useCallback(() => {
    setError(null);
    setAttempt((n) => n + 1);
  }, []);
  return <InfoContext value={{ info, error, reload }}>{children}</InfoContext>;
}

export function useInfo(): InfoState {
  return useContext(InfoContext);
}
