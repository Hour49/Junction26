import { useCallback, useEffect, useState } from 'react';
import {
  errorText,
  getDrawing,
  getIssues,
  getProject,
  issuesZipUrl,
  type DrawingView,
  type FileStatus,
  type Issue,
} from '../api';
import { keepPolling, plural } from '../ingest/ingest';
import { usePoll } from '../ingest/usePoll';
import { issuesChanged } from '../shell/issueCount';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { DocumentLists } from './DocumentLists';
import { IssueCard } from './IssueCard';
import { issueModel } from '../model3d/model3d';
import { documentIssues, needsYou } from './documents';
import { Button } from '@/components/ui/button';
import { Tip } from '@/components/ui/tip';
import { TIPS } from '../shell/tips';
import { MUTED, SMALL, TITLE } from './ui';

/** Route `#/p/<pid>/documents` (documents.md): the issues to answer, the drawings, every file. */
export function DocumentsScreen({
  projectId,
  pack = null,
}: {
  projectId: string;
  pack?: string | null;
}) {
  const load = useCallback((signal: AbortSignal) => getProject(projectId, { signal }), [projectId]);
  const { data: project, error, retry, set } = usePoll(load, keepPolling);
  const done = project?.state === 'done';
  const [issues, setIssues] = useState<{ list: Issue[] } | { error: unknown } | null>(null);
  const [reload, setReload] = useState(0);
  const [drawings, setDrawings] = useState<Record<string, DrawingView | null>>({});

  useEffect(() => {
    if (!done) return;
    const abort = new AbortController();
    getIssues(projectId, { signal: abort.signal, pack: pack ?? undefined }).then(
      (r) => {
        setIssues({ list: r.issues });
      },
      (e: unknown) => {
        if (!abort.signal.aborted) setIssues({ error: e });
      },
    );
    return () => {
      abort.abort();
    };
  }, [done, projectId, pack, reload]);

  const list = issues && 'list' in issues ? issues.list : null;
  const rows = list ? documentIssues(list) : [];
  // one getDrawing per drawing with a located issue; a failure shows that drawing's cards with no picture
  const wanted = [
    ...new Set(
      rows.flatMap((r) =>
        r.issue.drawing_id && r.issue.page !== null ? [r.issue.drawing_id] : [],
      ),
    ),
  ].filter((id) => !(id in drawings));
  const wantedKey = wanted.join(',');
  useEffect(() => {
    if (!wantedKey) return;
    for (const id of wantedKey.split(','))
      getDrawing(id).then(
        (d) => {
          setDrawings((m) => ({ ...m, [id]: d }));
        },
        () => {
          setDrawings((m) => ({ ...m, [id]: null }));
        },
      );
  }, [wantedKey]);

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

  const onFile = (file: FileStatus) => {
    set({ ...project, files: project.files.map((f) => (f.id === file.id ? file : f)) });
    setReload((n) => n + 1); // the issue's state follows the call
    issuesChanged(projectId); // and so does the header badge
  };
  const onIssue = (issue: Issue) => {
    if (list) setIssues({ list: list.map((i) => (i.id === issue.id ? issue : i)) });
    issuesChanged(projectId); // the header badge asks again
  };
  const q = pack ? `?pack=${encodeURIComponent(pack)}` : '';
  const left = list ? needsYou(list) : 0;
  const failed = issues && 'error' in issues ? errorText(issues.error) : null;

  return (
    <div className="v-page v-page--narrow [&_p]:m-0">
      <div className={TITLE}>
        <div>
          <span className="text-[13px] font-semibold text-ok [overflow-wrap:anywhere]">
            {project.name}
          </span>
          <h1 className="v-title m-0">Documents</h1>
          <p className={MUTED}>
            {plural(project.files.length, 'file')} ingested,{' '}
            {plural(project.drawings.length, 'drawing')} read from them
          </p>
        </div>
        <Button
          asChild
          variant="secondary"
          size="pill"
          className="v-press font-medium no-underline"
        >
          <a href={`#/p/${projectId}/checks${q}`}>Building-code checks</a>
        </Button>
      </div>
      <section aria-label="Issues" className="flex flex-col gap-3">
        <div className={TITLE}>
          <div>
            <Tip text={TIPS.issues} wrap>
              <h2 className="m-0 text-xl">Issues</h2>
            </Tip>
            {rows.length > 0 && (
              <p className={MUTED}>
                {left
                  ? `${plural(left, 'issue')} need${left === 1 ? 's' : ''} your answer.`
                  : 'Every issue is answered.'}{' '}
                Notes are for your information.
              </p>
            )}
          </div>
          {done && (
            <a
              className={`${SMALL} inline-flex min-h-11 items-center`}
              href={issuesZipUrl(projectId, pack ?? undefined)}
              download
            >
              Export
            </a>
          )}
        </div>
        {!done ? (
          <p className={MUTED}>The issues are listed once the project is read.</p>
        ) : failed ? (
          <p role="alert" className="text-danger">
            {failed.detail} ({failed.code}){' '}
            <Button
              variant="secondary"
              size="pill"
              className="v-press font-medium"
              onClick={() => {
                setIssues(null);
                setReload((n) => n + 1);
              }}
            >
              Retry
            </Button>
          </p>
        ) : list === null ? (
          <Loading label="Loading issues…" />
        ) : rows.length === 0 ? (
          <p className={MUTED}>No issues: nothing needs a look.</p>
        ) : (
          <ol className="m-0 flex list-none flex-col gap-2.5 p-0">
            {rows.map(({ issue, n }) => (
              <IssueCard
                key={issue.id}
                projectId={projectId}
                issue={issue}
                n={n}
                drawing={issue.drawing_id ? drawings[issue.drawing_id] : null}
                file={project.files.find((f) => f.id === issue.file_id)}
                model={issueModel(issue, project.files)}
                onFile={onFile}
                pack={pack}
                onIssue={onIssue}
              />
            ))}
          </ol>
        )}
      </section>
      <DocumentLists project={project} />
    </div>
  );
}
