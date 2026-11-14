import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  getDrawing,
  getIssues,
  issuesCsvUrl,
  issuesZipUrl,
  rulePacksOf,
  type DrawingView,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { Loading } from '../shell/Loading';
import { usePoll } from '../ingest/usePoll';
import { IssueList } from './IssueList';
import { IssuePlan } from './IssuePlan';
import {
  STATES,
  STATE_LABEL,
  counts,
  filterIssues,
  issueMarks,
  issueTones,
  kindOf,
  numbered,
} from './issues';
import './issues.css';

const once = () => false;
const NO_FILTER = { kind: '', state: '' };

/** Route `#/p/<pid>/issues` (issues.md): every place that needs a look, located, with the export. */
export function IssuesScreen({
  projectId,
  pack = null,
}: {
  projectId: string;
  pack?: string | null;
}) {
  const load = useCallback(
    (signal: AbortSignal) => getIssues(projectId, { signal, pack: pack ?? undefined }),
    [projectId, pack],
  );
  const { data, error, retry } = usePoll(load, once);
  const { info } = useInfo();
  const note = pack ? rulePacksOf(info).find((p) => p.id === pack)?.note : null;
  const [filter, setFilter] = useState({ ...NO_FILTER, pack });
  const [picked, setPicked] = useState<string | null>(null);
  const [drawings, setDrawings] = useState<Record<string, DrawingView | 'error'>>({});
  const asked = useRef(new Set<string>());
  if (filter.pack !== pack) setFilter({ ...NO_FILTER, pack }); // a new country: filters reset

  const rows = numbered(data?.issues ?? []);
  const selected =
    rows.find((r) => r.issue.id === picked)?.issue ??
    rows.find((r) => r.issue.drawing_id && r.issue.page !== null)?.issue ??
    null;
  const drawingId = selected?.drawing_id ?? null;

  useEffect(() => {
    if (!drawingId || asked.current.has(drawingId)) return;
    asked.current.add(drawingId); // once per drawing per visit
    getDrawing(drawingId, { project: projectId }).then(
      (d) => {
        setDrawings((all) => ({ ...all, [drawingId]: d }));
      },
      () => {
        setDrawings((all) => ({ ...all, [drawingId]: 'error' }));
      },
    );
  }, [drawingId, projectId]);

  function select(id: string, scroll: boolean) {
    setPicked(id);
    if (scroll) document.getElementById(`issue-${id}`)?.scrollIntoView({ block: 'nearest' });
    else document.querySelector('.is-plan')?.scrollIntoView({ block: 'nearest' });
  }

  const title = <h1 className="v-title">Issues</h1>;
  if (data === null) {
    const api = error instanceof ApiError ? error : null;
    let body =
      error === null ? (
        <Loading label="Loading issues…" />
      ) : (
        <ErrorView error={error} onRetry={retry} />
      );
    if (api?.status === 409)
      body = (
        <div className="v-card">
          <p>The issues are listed once the ingest is done.</p>
          <p className="is-links">
            <a href={`#/p/${projectId}`}>Back to the project</a>
            <button type="button" className="v-btn v-btn--secondary v-press" onClick={retry}>
              Retry
            </button>
          </p>
        </div>
      );
    else if (api?.status === 404 && api.code === 'unknown_pack')
      body = (
        <div className="v-card">
          <p>These country rules are not available.</p>
          <a href={`#/p/${projectId}/issues`}>Show the issues without country rules</a>
        </div>
      );
    return (
      <div className="v-page v-page--wide is-screen">
        {title}
        {body}
      </div>
    );
  }

  const shown = filterIssues(rows, filter);
  const present = <T extends string>(
    values: readonly T[],
    of: (i: (typeof rows)[number]['issue']) => T,
  ) =>
    values.flatMap((v) => {
      const n = rows.filter((r) => of(r.issue) === v).length;
      return n ? [{ v, n }] : [];
    });
  const kinds = present([...new Set(rows.map((r) => r.issue.kind))], (i) => i.kind);
  const states = present(STATES, (i) => i.state);
  const csvPack = pack ?? undefined;
  return (
    <div className="v-page v-page--wide is-screen">
      <header className="is-head">
        <div>
          {title}
          <p className="v-caption">{counts(data.issues)}</p>
        </div>
        <p className="is-export">
          <a
            className="v-btn v-press"
            href={issuesZipUrl(projectId, csvPack)}
            download
            data-pending="issues.zip"
          >
            Export
          </a>
          <a href={issuesCsvUrl(projectId, csvPack)} download>
            CSV only
          </a>
        </p>
      </header>
      <p className="v-caption">
        {pack ? (note ?? '') : 'Choose a country in the header to add building-code checks.'}
      </p>
      <div className="is-filters">
        <label>
          Kind
          <select
            value={filter.kind}
            onChange={(e) => {
              setFilter({ ...filter, kind: e.target.value });
            }}
          >
            <option value="">All</option>
            {kinds.map(({ v, n }) => (
              <option key={v} value={v}>{`${kindOf(v).word} (${String(n)})`}</option>
            ))}
          </select>
        </label>
        <label>
          State
          <select
            value={filter.state}
            onChange={(e) => {
              setFilter({ ...filter, state: e.target.value });
            }}
          >
            <option value="">All</option>
            {states.map(({ v, n }) => (
              <option key={v} value={v}>{`${STATE_LABEL[v].word} (${String(n)})`}</option>
            ))}
          </select>
        </label>
      </div>
      {rows.length === 0 ? (
        <p>
          {pack
            ? 'No issues: nothing needs a look, and no rule failed.'
            : 'No issues: nothing needs a look.'}
        </p>
      ) : (
        <div className="is-cols">
          <IssuePlan
            issue={selected}
            drawing={drawingId ? drawings[drawingId] : undefined}
            marks={drawingId ? issueMarks(rows, drawingId) : []}
            tones={drawingId ? issueTones(rows, drawingId) : {}}
            onSelect={(id) => {
              select(id, true);
            }}
          />
          <div className="is-lists">
            {shown.length === 0 ? (
              <p>
                No issue matches these filters.{' '}
                <button
                  type="button"
                  className="v-btn v-btn--secondary v-press"
                  onClick={() => {
                    setFilter({ ...NO_FILTER, pack });
                  }}
                >
                  Show all
                </button>
              </p>
            ) : (
              <IssueList
                rows={shown}
                selected={selected?.id ?? null}
                projectId={projectId}
                pack={pack}
                onSelect={(id) => {
                  select(id, false);
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
