import { useEffect, useState, useSyncExternalStore } from 'react';
import { getIssues, getProject } from '../api';
import { needsYou } from '../documents/documents';
import { rememberProjectName } from './title';

/** How often a running project is asked whether its ingest is done. */
const WAIT_MS = 1000;

// "The issues of this project changed" (an answer was posted): every badge and done line asks again.
const versions = new Map<string, number>();
const listeners = new Set<() => void>();

/** Call after `answerIssue` resolves: every `useIssuesToAnswer(projectId)` asks the server again. */
export function issuesChanged(projectId: string): void {
  versions.set(projectId, (versions.get(projectId) ?? 0) + 1);
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** The Documents badge number for a project (shared.md "Documents badge"): the server's `issues_to_answer` (#223),
 * else `needsYou` over its issues with `Issue.answer` as answered (always with a `pack`: the server count has no pack's
 * rule issues, SH-88); null while loading, on any error, for a failed
 * project and without a project. `reload` asks again when it changes (the header passes the route). */
export function useIssuesToAnswer(
  projectId: string | null,
  reload?: unknown,
  pack?: string | null,
): number | null {
  const [loaded, setLoaded] = useState<{ projectId: string; count: number } | null>(null);
  const version = useSyncExternalStore(subscribe, () =>
    projectId === null ? 0 : (versions.get(projectId) ?? 0),
  );

  useEffect(() => {
    if (projectId === null) return;
    const abort = new AbortController();
    const signal = abort.signal;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // The issues answer 409 until the ingest is done (a console error in the browser): wait for `done` first.
    const ask = async () => {
      const project = await getProject(projectId, { signal });
      rememberProjectName(projectId, project.name);
      if (project.state === 'queued' || project.state === 'running') {
        timer = setTimeout(() => {
          ask().catch(fail);
        }, WAIT_MS);
        return;
      }
      if (project.state !== 'done') {
        setLoaded(null);
        return;
      }
      let count = pack ? null : project.issues_to_answer;
      if (count === null || count === undefined) {
        count = needsYou((await getIssues(projectId, { signal, pack: pack ?? undefined })).issues);
      }
      setLoaded({ projectId, count });
    };
    const fail = () => {
      if (!signal.aborted) setLoaded(null);
    };
    ask().catch(fail);
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [projectId, reload, version, pack]);

  return projectId !== null && loaded?.projectId === projectId ? loaded.count : null;
}
