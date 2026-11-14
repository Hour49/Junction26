import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { getInfo, type Info } from '../api';

export interface InfoState {
  /** null until `GET /api/info` has answered. */
  info: Info | null;
  error: unknown;
  reload: () => void;
}

const InfoContext = createContext<InfoState>({ info: null, error: null, reload: () => undefined });

/** Asks `GET /api/info` once when the app starts, and again on `reload`. */
export function InfoProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    getInfo({ signal: abort.signal }).then(
      (found) => {
        setInfo(found);
        setError(null);
      },
      (failed: unknown) => {
        if (!abort.signal.aborted) setError(failed);
      },
    );
    return () => {
      abort.abort();
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
