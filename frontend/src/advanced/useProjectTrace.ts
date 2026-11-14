import { useCallback, useEffect, useState } from 'react';
import { getProjectTrace, type FileStatus, type FileTrace } from '../api';

export interface Traces {
  traces: ReadonlyMap<string, FileTrace>; // by file id
  failed: boolean;
  retry: () => void;
}

/**
 * The project's one trace (`GET /api/projects/{id}/trace`), requested when any file's `id|state|stage` changes,
 * never while no file has a stage. A newer request aborts the older one, and unmount aborts it. A failure keeps
 * the last traces and sets `failed` until `retry` or the next change.
 */
export function useProjectTrace(projectId: string, files: readonly FileStatus[]): Traces {
  const [traces, setTraces] = useState<ReadonlyMap<string, FileTrace>>(new Map());
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const started = files.some((f) => f.stage != null);
  const key = files.map((f) => `${f.id}|${f.state}|${f.stage ?? ''}`).join(',');

  useEffect(() => {
    if (!started) return;
    const controller = new AbortController();
    getProjectTrace(projectId, { signal: controller.signal }).then(
      (t) => {
        setTraces(new Map(t.files.map((f) => [f.file.id, f])));
        setFailed(false);
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        console.warn('trace not loaded', error);
        setFailed(true);
      },
    );
    return () => {
      controller.abort();
    };
  }, [projectId, key, started, attempt]);

  const retry = useCallback(() => {
    setAttempt((a) => a + 1);
  }, []);
  return { traces, failed, retry };
}
