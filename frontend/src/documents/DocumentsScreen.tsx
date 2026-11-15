import { useCallback } from 'react';
import { getProject } from '../api';
import { keepPolling } from '../ingest/ingest';
import { usePoll } from '../ingest/usePoll';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { DocumentLists } from './DocumentLists';
import { TITLE } from './ui';

/** Route `#/p/<pid>/documents` (documents.md): the project's drawings, each with its file's state. The issues
 * that waited here are asked for in the chat (P6a); `pack` is kept for the route's sake. */
export function DocumentsScreen({ projectId }: { projectId: string; pack?: string | null }) {
  const load = useCallback((signal: AbortSignal) => getProject(projectId, { signal }), [projectId]);
  const { data: project, error, retry } = usePoll(load, keepPolling);

  if (project === null)
    return (
      <div className="v-page v-page--narrow [&_p]:m-0">
        {error !== null ? (
          <ErrorView error={error} onRetry={retry} />
        ) : (
          <Loading label="Loading documents…" />
        )}
      </div>
    );

  return (
    <div className="v-page v-page--narrow [&_p]:m-0">
      <div className={TITLE}>
        <div>
          <span className="text-[13px] font-semibold text-ok [overflow-wrap:anywhere]">
            {project.name}
          </span>
          <h1 className="v-title m-0">Documents</h1>
        </div>
      </div>
      <DocumentLists project={project} />
    </div>
  );
}
