import { useEffect, useState } from 'react';
import { getIssues, type Issue } from '../api';
import { needsYou } from '../documents/documents';
import { useIssueAnswers } from './issueAnswers';

/** The Documents badge number for a project (`needsYou` over its issues and typed answers); null while loading, on
 * any error (a 409 before the ingest is done) and without a project. `reload` asks again when it changes (the
 * header passes the route). */
export function useIssuesToAnswer(projectId: string | null, reload?: unknown): number | null {
  const [loaded, setLoaded] = useState<{ projectId: string; issues: Issue[] } | null>(null);
  const answers = useIssueAnswers(projectId ?? '');

  useEffect(() => {
    if (projectId === null) return;
    const abort = new AbortController();
    getIssues(projectId, { signal: abort.signal }).then(
      (list) => {
        setLoaded({ projectId, issues: list.issues });
      },
      () => {
        if (!abort.signal.aborted) setLoaded(null);
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, reload]);

  if (projectId === null || loaded?.projectId !== projectId) return null;
  return needsYou(loaded.issues, answers);
}
