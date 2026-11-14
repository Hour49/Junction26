// Screen 5, #/workspaces: every workspace on this server and the selected one's stats and history
// (docs/specs/frontend/account.md). No login, so no user name or avatar.
import { useCallback, useState } from 'react';
import {
  errorText,
  formatTime,
  getProject,
  getProjectReview,
  getTakeoff,
  listProjects,
  type ProjectReview,
  type ProjectSummary,
} from '../api';
import { usePoll } from '../ingest/usePoll';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { historyEvents, workspaceKind, workspacePill, workspaceStats } from './history';
import { toReviewOf } from './pending';
import './account.css';

const once = () => false;
const loadList = (signal: AbortSignal) => listProjects({ signal });

export function AccountScreen() {
  const list = usePoll(loadList, once);
  const [selected, setSelected] = useState<string | null>(null);
  // Reviews of the workspaces opened on this page: they back the list's "to review" pill.
  const [reviews, setReviews] = useState<Record<string, ProjectReview>>({});
  const onReview = useCallback((id: string, review: ProjectReview) => {
    setReviews((all) => ({ ...all, [id]: review }));
  }, []);

  const projects = list.data?.projects ?? [];
  const current = projects.find((p) => p.id === selected) ?? projects[0];

  return (
    <main className="account">
      <div className="account-top">
        <div>
          <h1>Your workspaces</h1>
          {list.data && (
            <p className="v-caption">
              {projects.length === 1 ? '1 workspace' : `${String(projects.length)} workspaces`} on
              this server
            </p>
          )}
        </div>
        <a className="v-btn account-new" href="#/">
          <span aria-hidden="true">+</span> New workspace
        </a>
      </div>
      {list.error && !list.data ? (
        <ErrorView error={list.error} onRetry={list.retry} />
      ) : !list.data ? (
        <Loading label="Loading workspaces…" />
      ) : !current ? (
        <p className="account-empty">
          No workspaces yet. <a href="#/">Drop files or try a sample</a>
        </p>
      ) : (
        <div className="account-body">
          <ul className="account-list">
            {projects.map((p) => (
              <li key={p.id}>
                <Item
                  summary={p}
                  review={reviews[p.id] ?? null}
                  pressed={p.id === current.id}
                  onSelect={() => {
                    setSelected(p.id);
                  }}
                />
              </li>
            ))}
          </ul>
          <Panel key={current.id} summary={current} onReview={onReview} />
        </div>
      )}
    </main>
  );
}

function Item({
  summary,
  review,
  pressed,
  onSelect,
}: {
  summary: ProjectSummary;
  review: ProjectReview | null;
  pressed: boolean;
  onSelect: () => void;
}) {
  const pill = workspacePill(summary.state);
  const open = toReviewOf(summary, review);
  return (
    <button type="button" className="account-item" aria-pressed={pressed} onClick={onSelect}>
      <span className="account-item-head">
        <span className="account-name">{summary.name}</span>
        <span className={`v-pill v-pill--${pill.tone}`}>{pill.word}</span>
        {open && open.n > 0 && (
          <span
            className="v-pill v-pill--warn"
            {...(open.pending && { 'data-pending': 'ProjectSummary.to_review' })}
          >
            {open.n} to review
          </span>
        )}
      </span>
      <span className="v-caption">{workspaceKind(summary)}</span>
      <span className="v-caption">{formatTime(summary.created_at)}</span>
    </button>
  );
}

function Panel({
  summary,
  onReview,
}: {
  summary: ProjectSummary;
  onReview: (id: string, review: ProjectReview) => void;
}) {
  const id = summary.id;
  const project = usePoll(
    useCallback((signal: AbortSignal) => getProject(id, { signal }), [id]),
    once,
  );
  const review = usePoll(
    useCallback(
      async (signal: AbortSignal) => {
        const r = await getProjectReview(id, { signal });
        onReview(id, r);
        return r;
      },
      [id, onReview],
    ),
    once,
  );
  const reviewData = review.error ? null : review.data;
  const signed = reviewData?.drawings.filter((d) => d.signed > 0) ?? [];
  const takeoffs = usePoll(
    useCallback(
      (signal: AbortSignal) =>
        Promise.all(signed.map((d) => getTakeoff(d.drawing_id, { project: id, signal }))),
      // Only a new review changes which drawings are asked for.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [id, reviewData],
    ),
    once,
  );

  let body;
  if (project.error) {
    body = <ErrorView error={project.error} onRetry={project.retry} />;
  } else if (!project.data) {
    body = <Loading label={`Loading ${summary.name}…`} />;
  } else {
    const p = project.data;
    const events = historyEvents(p, reviewData, takeoffs.error ? [] : (takeoffs.data ?? []));
    const reviewError = review.error ? errorText(review.error) : null;
    const takeoffError = takeoffs.error ? errorText(takeoffs.error) : null;
    body = (
      <>
        <div className="account-panel-head">
          <div>
            <p className="v-caption">
              {p.files.length === 1 ? 'Single file' : 'Archive'} · created{' '}
              {formatTime(p.created_at)}
            </p>
            <h2 className="account-name">{p.name}</h2>
          </div>
          <a className="v-btn v-btn--secondary" href={`#/p/${id}`}>
            Open workspace
          </a>
        </div>
        <dl className="account-stats">
          {workspaceStats(p, reviewData).map((s) => (
            <div key={s.label} {...(s.pending && { 'data-pending': s.pending })}>
              <dt>{s.label}</dt>
              <dd>{s.value}</dd>
            </div>
          ))}
        </dl>
        {reviewError && (
          <p className="account-note" role="alert">
            Review not loaded: {reviewError.detail} ({reviewError.code}){' '}
            <button type="button" className="v-btn v-btn--secondary" onClick={review.retry}>
              Retry
            </button>
          </p>
        )}
        <h3>History</h3>
        <ol className="account-history">
          {events.map((e, i) => (
            <li key={`${e.kind}-${String(i)}`} className={`account-event account-event--${e.kind}`}>
              <time dateTime={e.at} {...(e.pending && { 'data-pending': e.pending })}>
                {e.time}
              </time>
              <span className="account-glyph" aria-hidden="true">
                {e.glyph}
              </span>
              <span className="account-event-text">
                <strong>{e.title}</strong>
                <span className="v-caption">{e.detail}</span>
              </span>
            </li>
          ))}
        </ol>
        {takeoffError && (
          <p className="account-note" role="alert">
            Sign-offs not loaded: {takeoffError.detail} ({takeoffError.code})
          </p>
        )}
      </>
    );
  }
  return (
    <section className="v-card account-panel" aria-label="Selected workspace">
      {body}
    </section>
  );
}
