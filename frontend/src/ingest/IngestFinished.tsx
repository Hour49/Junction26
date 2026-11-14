// What a finished ingest shows under its progress card (ingest.md v3, demo parity): the done line, fe-surveyor's
// conflicts list and the chat row. Simple places them here; fe-scaffold's Advanced view imports the same pieces.
import { useCallback, useState, type JSX } from 'react';
import type { ProjectView } from '../api';
import { useIssuesToAnswer } from '../shell/issueCount';
import { ConflictsList, type ConflictCounts } from '../surveyor/ConflictsScreen';
import { plural } from './ingest';

/** What the conflicts list reports after each load or settle (fe-surveyor's `onCounts`). */
export type { ConflictCounts };

/** The id of `ConflictsList`'s own section, to scroll to (never a `#` link: the router owns the hash). */
export const CONFLICTS_ID = 'conflicts';

const finished = (p: ProjectView) => p.state === 'done' && p.drawings.length > 0;

/** "5 drawings ready. Conflicts are below. 2 issues in Documents need you." (IN-76) */
export function DoneLine({
  projectId,
  project,
  counts,
}: {
  projectId: string;
  project: ProjectView;
  counts: ConflictCounts | null;
}): JSX.Element | null {
  // the Documents badge's own count, so the line and the badge never disagree; null while unknown
  const issues = useIssuesToAnswer(projectId);
  if (!finished(project)) return null;
  return (
    <p className="ingest-done-line">
      {`${plural(project.drawings.length, 'drawing')} ready.`}
      {counts !== null && counts.total > 0 && ' Conflicts are below.'}
      {issues !== null && issues > 0 && (
        <>
          {' '}
          <a href={`#/p/${projectId}/documents`}>{`${plural(issues, 'issue')} in Documents`}</a>
          {issues === 1 ? ' needs you.' : ' need you.'}
        </>
      )}
    </p>
  );
}

/** The conflicts list, then "Start a new chat" (locked while a conflict needs a person) and "Open the workspace". */
export function IngestFinished({
  projectId,
  project,
  query,
  onCounts,
}: {
  projectId: string;
  project: ProjectView;
  query?: URLSearchParams;
  onCounts?: (counts: ConflictCounts) => void;
}): JSX.Element | null {
  const [counts, setCounts] = useState<ConflictCounts | null>(null);
  const report = useCallback(
    (c: ConflictCounts) => {
      setCounts(c);
      onCounts?.(c);
    },
    [onCounts],
  );
  if (!finished(project)) return null;
  // locked until the list has said nothing needs a person (IN-77)
  const locked = counts === null || counts.needsPerson > 0;
  const first = project.drawings[0];
  return (
    <>
      <ConflictsList projectId={projectId} query={query} onCounts={report} />
      <div className="ingest-chat-row">
        {locked ? (
          <>
            <button
              type="button"
              className="v-btn v-press"
              disabled
              aria-describedby="ingest-chat-why"
            >
              Start a new chat
            </button>
            <span id="ingest-chat-why" className="ingest-chat-why">
              Settle the conflicts that need you first.
            </span>
          </>
        ) : (
          <>
            <a className="v-btn v-press" href={`#/p/${projectId}/chat`}>
              Start a new chat
            </a>
            {first && (
              <a
                className="ingest-chat-link"
                href={`#/p/${projectId}/d/${first.drawing_id}/engineer`}
              >
                Open the workspace
              </a>
            )}
          </>
        )}
      </div>
    </>
  );
}
