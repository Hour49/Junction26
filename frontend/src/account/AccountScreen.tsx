// Screen 5, #/workspaces: every workspace on this server and the selected one's stats and history
// (docs/specs/frontend/account.md). No login, so no user name or avatar.
import { useCallback, useState } from 'react';
import {
  errorText,
  formatTime,
  getProject,
  getProjectQuestions,
  getProjectReview,
  getTakeoff,
  listProjects,
  type ProjectSummary,
} from '../api';
import { usePoll } from '../ingest/usePoll';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { historyEvents, workspaceKind, workspacePill, workspaceStats } from './history';
import './account.css';

const once = () => false;
const loadList = (signal: AbortSignal) => listProjects({ signal });

export function AccountScreen() {
  const list = usePoll(loadList, once);
  const [selected, setSelected] = useState<string | null>(null);

  const projects = list.data?.projects ?? [];
  const current = projects.find((p) => p.id === selected) ?? projects[0];

  return (
    <div className="account">
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
                  pressed={p.id === current.id}
                  onSelect={() => {
                    setSelected(p.id);
                  }}
                />
              </li>
            ))}
          </ul>
          <Panel key={current.id} summary={current} />
        </div>
      )}
    </div>
  );
}

function Item({
  summary,
  pressed,
  onSelect,
}: {
  summary: ProjectSummary;
  pressed: boolean;
  onSelect: () => void;
}) {
  const pill = workspacePill(summary.state);
  // Null until the workspace is done: then no pill. `conflicts_open` is not shown: the API counts conflicts a rule
  // settled as open, while the conflicts screen calls them settled (account.md).
  const toReview = summary.to_review ?? 0;
  return (
    <button type="button" className="account-item" aria-pressed={pressed} onClick={onSelect}>
      <span className="account-item-head">
        <span className="account-name">{summary.name}</span>
        <span className={`v-pill v-pill--${pill.tone}`}>{pill.word}</span>
        {toReview > 0 && <span className="v-pill v-pill--warn">{toReview} to review</span>}
      </span>
      <span className="v-caption">{workspaceKind(summary)}</span>
      <span className="v-caption">{formatTime(summary.created_at)}</span>
    </button>
  );
}

function Panel({ summary }: { summary: ProjectSummary }) {
  const id = summary.id;
  const project = usePoll(
    useCallback((signal: AbortSignal) => getProject(id, { signal }), [id]),
    once,
  );
  const review = usePoll(
    useCallback((signal: AbortSignal) => getProjectReview(id, { signal }), [id]),
    once,
  );
  const questions = usePoll(
    useCallback((signal: AbortSignal) => getProjectQuestions(id, { signal }), [id]),
    once,
  );
  const questionsData = questions.error ? null : questions.data;
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
    const events = historyEvents(
      p,
      reviewData,
      takeoffs.error ? [] : (takeoffs.data ?? []),
      questionsData,
    );
    const reviewError = review.error ? errorText(review.error) : null;
    const questionsError = questions.error ? errorText(questions.error) : null;
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
          <a className="v-btn account-open" href={`#/p/${id}`}>
            Open workspace
          </a>
        </div>
        <dl className="account-stats">
          {workspaceStats(p, reviewData, questionsData).map((s) => (
            <div key={s.label}>
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
        {questionsError && (
          <p className="account-note" role="alert">
            Questions not loaded: {questionsError.detail} ({questionsError.code}){' '}
            <button type="button" className="v-btn v-btn--secondary" onClick={questions.retry}>
              Retry
            </button>
          </p>
        )}
        <h3>History</h3>
        <ol className="account-history">
          {events.map((e, i) => (
            <li key={`${e.kind}-${String(i)}`} className={`account-event account-event--${e.kind}`}>
              <time dateTime={e.at}>{e.time}</time>
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
