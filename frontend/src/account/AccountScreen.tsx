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
  type ProjectList,
  type ProjectReview,
  type ProjectSummary,
} from '../api';
import { usePoll } from '../ingest/usePoll';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { historyEvents, workspaceKind, workspacePill, workspaceStats } from './history';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const once = () => false;
const NAME = 'min-w-0 font-mono font-semibold [overflow-wrap:anywhere]';
const PILL = 'px-[11px] py-[5px] text-xs';
/** The history glyph's colour by event kind; the rest are accent. */
const GLYPH: Record<string, string> = {
  failed: 'bg-warn-soft text-warn',
  needs: 'bg-warn-soft text-warn',
  signed: 'bg-ok-soft text-ok',
  done: 'bg-ok-soft text-ok',
};
const loadList = (signal: AbortSignal) => listProjects({ signal });

/** A sign-off made just before Workspaces opened can land after the first answer (AC-36): while something is
 * still to review, ask again (usePoll's 500 ms) for at most this long after the screen opened. */
const SETTLE_MS = 5000;
function useUntilSettled<T>(toReview: (data: T) => number): (data: T) => boolean {
  const [opened] = useState(() => Date.now());
  return useCallback(
    (data: T) => toReview(data) > 0 && Date.now() - opened < SETTLE_MS,
    [opened, toReview],
  );
}
const listToReview = (l: ProjectList) => l.projects.reduce((n, p) => n + (p.to_review ?? 0), 0);
const reviewToReview = (r: ProjectReview) => r.drawings.reduce((n, d) => n + d.to_review, 0);

export function AccountScreen() {
  const list = usePoll(loadList, useUntilSettled(listToReview));
  const [selected, setSelected] = useState<string | null>(null);

  const projects = list.data?.projects ?? [];
  const current = projects.find((p) => p.id === selected) ?? projects[0];

  return (
    <div className="account mx-auto max-w-[1280px] px-6 py-10 max-[720px]:px-4 max-[720px]:py-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-[44px] leading-[1.1] font-bold tracking-[-0.025em] max-[720px]:text-[32px]">
            Your workspaces
          </h1>
          {list.data && (
            <p className="v-caption mt-1.5 mb-0">
              {projects.length === 1 ? '1 workspace' : `${String(projects.length)} workspaces`} on
              this server
            </p>
          )}
        </div>
        <Button asChild size="pill" className="no-underline hover:text-primary-foreground">
          <a href="#/">
            <span aria-hidden="true">+</span> New workspace
          </a>
        </Button>
      </div>
      {list.error && !list.data ? (
        <ErrorView error={list.error} onRetry={list.retry} />
      ) : !list.data ? (
        <Loading label="Loading workspaces…" />
      ) : !current ? (
        <p>
          No workspaces yet.{' '}
          <a className="ml-1" href="#/">
            Drop files or try a sample
          </a>
        </p>
      ) : (
        <div className="flex items-start gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
          <ul className="account-list m-0 grid max-w-[400px] min-w-0 flex-[1_1_320px] list-none gap-3 p-0 max-[720px]:max-w-none max-[720px]:flex-none">
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
    <button
      type="button"
      className={cn(
        'grid min-h-11 w-full cursor-pointer gap-1 rounded-[18px] border border-border bg-card p-4 text-left text-foreground',
        pressed && 'border-2 border-primary p-[15px]',
      )}
      aria-pressed={pressed}
      onClick={onSelect}
    >
      <span className="flex flex-wrap items-center gap-2">
        <span className={NAME}>{summary.name}</span>
        <Badge variant={pill.tone} className={PILL}>
          {pill.word}
        </Badge>
        {toReview > 0 && (
          <Badge variant="warn" className={PILL}>
            {toReview} to review
          </Badge>
        )}
        {(summary.conflicts_picked ?? 0) > 0 && (
          <Badge variant="secondary" className={cn(PILL, 'text-text-2')}>
            {summary.conflicts_picked} picked by Carbon
          </Badge>
        )}
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
    useUntilSettled(reviewToReview),
  );
  const questions = usePoll(
    useCallback((signal: AbortSignal) => getProjectQuestions(id, { signal }), [id]),
    once,
  );
  const questionsData = questions.error ? null : questions.data;
  const reviewData = review.error ? null : review.data;
  // A review asked again (AC-36) is a new object with the same content: only new content asks for the takeoffs.
  const reviewKey = reviewData ? JSON.stringify(reviewData) : null;
  // Every drawing with rows: the Signed off stat counts disagreements over them (account.md).
  const measured = reviewData?.drawings.filter((d) => d.quantities > 0) ?? [];
  const takeoffs = usePoll(
    useCallback(
      (signal: AbortSignal) =>
        Promise.all(measured.map((d) => getTakeoff(d.drawing_id, { project: id, signal }))),
      // Only a review with new content changes which drawings are asked for, and what they hold.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [id, reviewKey],
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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="v-caption m-0">
              {p.files.length === 1 ? 'Single file' : 'Archive'} · created{' '}
              {formatTime(p.created_at)}
            </p>
            <h2 className={cn(NAME, 'mt-1 mb-0 text-2xl')}>{p.name}</h2>
          </div>
          <Button
            asChild
            size="pill"
            className="bg-accent text-accent-strong no-underline hover:bg-accent hover:text-accent-strong"
          >
            <a href={`#/p/${id}`}>Open workspace</a>
          </Button>
        </div>
        <dl className="my-6 grid grid-cols-5 border-y border-border [&>div]:border-border [&>div]:border-l [&>div]:px-4 [&>div]:py-3 [&>div:first-child]:border-l-0 max-[720px]:grid-cols-2 max-[720px]:[&>div]:border-b max-[720px]:[&>div]:border-l-0 max-[720px]:[&>div:nth-child(5)]:col-span-full">
          {workspaceStats(
            p,
            reviewData,
            questionsData,
            // Until every drawing's takeoff is in (the first load answers [] before the review), "–".
            reviewData && !takeoffs.error && takeoffs.data?.length === measured.length
              ? takeoffs.data
              : null,
          ).map((s) => (
            <div key={s.label}>
              <dt className="text-[13px] text-muted-foreground">{s.label}</dt>
              <dd className="m-0 mt-0.5 text-2xl font-bold whitespace-nowrap">{s.value}</dd>
            </div>
          ))}
        </dl>
        {reviewError && (
          <p className="text-danger" role="alert">
            Review not loaded: {reviewError.detail} ({reviewError.code}){' '}
            <Button variant="secondary" size="pill" className="font-medium" onClick={review.retry}>
              Retry
            </Button>
          </p>
        )}
        {questionsError && (
          <p className="text-danger" role="alert">
            Questions not loaded: {questionsError.detail} ({questionsError.code}){' '}
            <Button
              variant="secondary"
              size="pill"
              className="font-medium"
              onClick={questions.retry}
            >
              Retry
            </Button>
          </p>
        )}
        <h3 className="mt-0 mb-3 text-[17px]">History</h3>
        <ol className="m-0 grid list-none gap-3.5 p-0">
          {events.map((e, i) => (
            <li
              key={`${e.kind}-${String(i)}`}
              className="grid grid-cols-[52px_28px_minmax(0,1fr)] items-start gap-2.5"
            >
              <time className="pt-1 font-mono text-[13px] text-muted-foreground" dateTime={e.at}>
                {e.time}
              </time>
              <span
                className={cn(
                  'grid size-7 place-items-center rounded-full text-sm',
                  GLYPH[e.kind] ?? 'bg-accent text-accent-strong',
                )}
                aria-hidden="true"
              >
                {e.glyph}
              </span>
              <span className="grid gap-0.5 [overflow-wrap:anywhere]">
                <strong>{e.title}</strong>
                <span className="v-caption">{e.detail}</span>
              </span>
            </li>
          ))}
        </ol>
        {takeoffError && (
          <p className="text-danger" role="alert">
            Sign-offs not loaded: {takeoffError.detail} ({takeoffError.code})
          </p>
        )}
      </>
    );
  }
  return (
    <Card
      role="region"
      aria-label="Selected workspace"
      className="block min-w-0 flex-[2_1_0] rounded-[22px] border-0 p-6 shadow-[var(--v-shadow)] max-[720px]:p-5"
    >
      {body}
    </Card>
  );
}
