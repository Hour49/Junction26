import { useCallback, useEffect, useState } from 'react';
import {
  errorText,
  getDrawing,
  getIssues,
  getProject,
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
import { documentIssues, isAnswerable, needsYou, waitsForYou } from './documents';
import { Button } from '@/components/ui/button';
import { Tip } from '@/components/ui/tip';
import { TIPS } from '../shell/tips';
import { MUTED, TITLE } from './ui';

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
  // answered on this visit: kept on screen (Answered, Change, Undo) until the page is left
  const [answeredHere, setAnsweredHere] = useState<ReadonlySet<string>>(new Set());
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
  // Issues on demand: what waits for the person's answer now, the answerable notes still open (the call on a file
  // triage set aside: answerable, not counted, documents.md DOC-7), and what they answered on this visit
  const answerableOpen = (i: Issue) => isAnswerable(i) && i.state === 'open' && !i.answer;
  const rows = list
    ? documentIssues(
        list.filter((i) => waitsForYou(i) || answerableOpen(i) || answeredHere.has(i.id)),
      )
    : [];
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

  const keep = (ids: string[]) => {
    setAnsweredHere((s) => new Set([...s, ...ids]));
  };
  const onFile = (file: FileStatus) => {
    keep((list ?? []).filter((i) => i.file_id === file.id).map((i) => i.id));
    set({ ...project, files: project.files.map((f) => (f.id === file.id ? file : f)) });
    setReload((n) => n + 1); // the issue's state follows the call
    issuesChanged(projectId); // and so does the header badge
  };
  const onIssue = (issue: Issue) => {
    keep([issue.id]);
    if (list) setIssues({ list: list.map((i) => (i.id === issue.id ? issue : i)) });
    issuesChanged(projectId); // the header badge asks again
  };
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
        </div>
      </div>
      <section aria-label="Issues on demand" className="flex flex-col gap-3">
        <div className={TITLE}>
          <div>
            <Tip text={TIPS.issues} wrap>
              <h2 className="m-0 text-xl">Issues on demand</h2>
            </Tip>
            {rows.length > 0 && left > 0 && (
              <p className={MUTED}>
                {`${plural(left, 'issue')} need${left === 1 ? 's' : ''} your answer now.`}
              </p>
            )}
          </div>
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
          <p className={MUTED}>Nothing needs your answer right now.</p>
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
