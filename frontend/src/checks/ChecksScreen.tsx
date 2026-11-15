import { Tip } from '@/components/ui/tip';
import { REVIEW_TIPS } from '../shell/tips-review';
import { useEffect, useRef, useState, type JSX } from 'react';
import {
  ApiError,
  getDrawing,
  getProject,
  getProjectChecks,
  rulePacksOf,
  type DrawingView,
  type ProjectView,
} from '../api';
import { PROJECT_STATE_LABEL, plural } from '../ingest/ingest';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { Loading } from '../shell/Loading';
import { PageViewer } from '../viewer/PageViewer';
import {
  STATUS_WORD,
  drawingResults,
  drawingName,
  focusOf,
  limitLine,
  ruleCheckStatus,
  ruleSummary,
  viewerMarks,
} from './checks';
import type { CheckResult, ProjectChecks, RuleCheck } from './types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

const NOT_DONE = 'The pre-check runs once the drawings are read.';
const LINE = 'm-0 text-[17px]';
const MUTED = 'text-muted-foreground';
/** "cannot tell" is its own look: never the pass or fail colours. */
const STATUS_BADGE = { fail: 'danger', cannot_tell: 'warn', pass: 'outline' } as const;
/** At 390 px the table becomes one card per rule: the header hides, each cell says its column. */
const CELL =
  'px-4 py-2.5 text-right tabular-nums max-[600px]:text-left max-[600px]:before:block max-[600px]:before:text-xs max-[600px]:before:text-muted-foreground max-[600px]:before:content-[attr(data-label)]';

type Load<T> =
  { state: 'loading' } | { state: 'ok'; value: T } | { state: 'error'; error: unknown };
type Keyed<T> = { key: string; load: Load<T> };

const isFinished = (p: ProjectView) => p.state === 'done' || p.state === 'failed';
const notYet = (e: unknown) => e instanceof ApiError && e.status === 409;
const unknownPack = (e: unknown) =>
  e instanceof ApiError && e.status === 404 && e.code === 'unknown-pack';

/** The building-code pre-check of a project for one rule pack (docs/specs/frontend/checks.md). */
export function ChecksScreen({
  projectId,
  pack,
}: {
  projectId: string;
  pack: string | null;
}): JSX.Element {
  const rulePack = rulePacksOf(useInfo().info).find((p) => p.id === pack) ?? null;
  // Each answer is stored with the request it answers; a different key means that request is still loading.
  const [projectAnswer, setProject] = useState<Keyed<ProjectView> | null>(null);
  const [checksAnswer, setChecks] = useState<Keyed<ProjectChecks> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [pickedAnswer, setPicked] = useState<{
    key: string;
    drawingId: string;
    result: CheckResult;
  } | null>(null);
  const [views, setViews] = useState<ReadonlyMap<string, Load<DrawingView>>>(new Map());

  const hasPack = pack !== null;
  useEffect(() => {
    if (!hasPack) return;
    const abort = new AbortController();
    getProject(projectId, { signal: abort.signal }).then(
      (value) => {
        setProject({ key: projectId, load: { state: 'ok', value } });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setProject({ key: projectId, load: { state: 'error', error } });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, hasPack]);
  const project: Load<ProjectView> =
    projectAnswer?.key === projectId ? projectAnswer.load : { state: 'loading' };

  const finished = project.state === 'ok' && isFinished(project.value);
  const checksKey = `${projectId}|${pack ?? ''}|${String(attempt)}`;
  useEffect(() => {
    if (!pack || !finished) return;
    const abort = new AbortController();
    getProjectChecks(projectId, { pack, signal: abort.signal }).then(
      (value) => {
        setChecks({ key: checksKey, load: { state: 'ok', value } });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setChecks({ key: checksKey, load: { state: 'error', error } });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, pack, finished, checksKey]);
  const checks: Load<ProjectChecks> =
    checksAnswer?.key === checksKey ? checksAnswer.load : { state: 'loading' };
  // A pick belongs to one pack's answer: a new pack or a retry clears it.
  const picked = pickedAnswer?.key === checksKey ? pickedAnswer : null;

  // Each drawing's pages, asked on the first "Show on the drawing" (again after a failure); unmount aborts.
  const loads = useRef(new Set<AbortController>());
  useEffect(() => {
    const all = loads.current;
    return () => {
      for (const a of all) a.abort();
    };
  }, []);
  const loadDrawing = (did: string) => {
    const known = views.get(did);
    if (known && known.state !== 'error') return;
    const abort = new AbortController();
    loads.current.add(abort);
    setViews((m) => new Map(m).set(did, { state: 'loading' }));
    getDrawing(did, { project: projectId, signal: abort.signal })
      .then(
        (value) => {
          setViews((m) => new Map(m).set(did, { state: 'ok', value }));
        },
        (error: unknown) => {
          if (!abort.signal.aborted)
            setViews((m) => new Map(m).set(did, { state: 'error', error }));
        },
      )
      .finally(() => loads.current.delete(abort));
  };

  const page = (body: JSX.Element) => (
    <div className="v-page flex flex-col gap-4 motion-reduce:[&_*]:animate-none motion-reduce:[&_*]:transition-none">
      {body}
    </div>
  );
  if (!pack)
    return page(<p className={LINE}>Choose a country in the header to run its pre-check.</p>);
  if (project.state === 'loading') return page(<Loading label="Loading the checks…" />);
  if (project.state === 'error') return page(<ErrorView error={project.error} />);
  const p = project.value;

  const head = () => (
    <header>
      <h1 className="m-0 text-[clamp(26px,3vw,34px)] tracking-[-0.02em]">
        <Tip text={REVIEW_TIPS.preCheck} wrap>
          <span>Pre-check: {rulePack?.name ?? pack}</span>
        </Tip>
      </h1>
    </header>
  );

  if (!isFinished(p))
    return page(
      <>
        {head()}
        <p className={LINE}>{NOT_DONE}</p>
        <p className={MUTED}>Project: {PROJECT_STATE_LABEL[p.state] ?? p.state}</p>
      </>,
    );
  if (checks.state === 'loading')
    return page(
      <>
        {head()}
        <Loading label="Loading the checks…" />
      </>,
    );
  if (checks.state === 'error') {
    const e = checks.error;
    return page(
      <>
        {head()}
        {notYet(e) ? (
          <p className={LINE}>{NOT_DONE}</p>
        ) : unknownPack(e) ? (
          <p className={LINE}>These rules are not available. Pick another country in the header.</p>
        ) : (
          <ErrorView
            error={e}
            onRetry={() => {
              setAttempt((n) => n + 1);
            }}
          />
        )}
      </>,
    );
  }

  const c = checks.value;
  const rows = ruleSummary(c, rulePack);
  const order = new Map(p.drawings.map((d, i) => [d.drawing_id, i]));
  const drawings = [...c.drawings].sort(
    (a, b) => (order.get(a.drawing_id) ?? Infinity) - (order.get(b.drawing_id) ?? Infinity),
  );
  const listed = drawings.map((d) => ({
    d,
    results: drawingResults(d),
    applies: d.rules.some((r) => ruleCheckStatus(r) !== null),
  }));
  // a drawing no rule applies to passed nothing: it is counted apart, never as passing (not_applicable)
  const clean = listed.filter((x) => x.applies && !x.results.length).length;
  const none = listed.filter((x) => !x.applies).length;
  // r null: the rule cannot tell on this drawing without any result (nothing read): its own why, no value or place
  const card = (did: string, file: string, rule: RuleCheck, r: CheckResult | null) => {
    const status = r?.status ?? 'cannot_tell';
    const word = STATUS_WORD[status];
    const id = r?.id ?? `rule-${rule.rule_id}`;
    const subject = r && (r.subject.label || `${r.subject.kind} ${r.subject.ref ?? ''}`.trim());
    const located = r !== null && focusOf(r) !== null;
    const isPicked = r !== null && picked?.result.id === r.id && picked.drawingId === did;
    return (
      <li key={`${rule.rule_id}-${id}`}>
        <article
          className={cn(
            `ck-card ck-${status}`,
            'rounded-[18px] border-2 border-transparent bg-card p-4 text-card-foreground shadow-[var(--v-shadow)] [overflow-wrap:anywhere] aria-[current=true]:border-primary [&_p]:my-1.5',
          )}
          aria-current={isPicked ? 'true' : undefined}
          aria-labelledby={`ck-${did}-${id}`}
        >
          <p>
            <Badge variant={STATUS_BADGE[status]} className="px-2.5 py-0.5 text-base font-semibold">
              <span aria-hidden="true">{word.icon}</span> {word.word}
            </Badge>
          </p>
          <h3 className="my-1 text-base" id={`ck-${did}-${id}`}>
            {subject ? `${subject} · ${rule.title}` : rule.title}
          </h3>
          <p className={cn('font-mono text-sm', MUTED)}>File: {file}</p>
          {r && <p className="tabular-nums">{limitLine(r)}</p>}
          <p>{r?.why ?? rule.why}</p>
          <p className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {r && located ? (
              <Button
                variant="secondary"
                size="pill"
                className="px-4 text-base"
                onClick={() => {
                  setPicked({ key: checksKey, drawingId: did, result: r });
                  loadDrawing(did);
                }}
              >
                Show on the drawing
              </Button>
            ) : (
              <span className={MUTED}>Not located on the drawing</span>
            )}
          </p>
        </article>
      </li>
    );
  };

  const viewer = () => {
    if (!picked) return null;
    const v = views.get(picked.drawingId);
    if (!v || v.state === 'loading') return <Loading label="Loading the drawing…" />;
    if (v.state === 'error')
      return (
        <p className={MUTED}>
          Page not available.{' '}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              loadDrawing(picked.drawingId);
            }}
          >
            Retry
          </Button>
        </p>
      );
    const { marks, tones } = viewerMarks(picked.result);
    return (
      <PageViewer
        file={drawingName(p, {
          drawing_id: picked.drawingId,
          file: c.drawings.find((d) => d.drawing_id === picked.drawingId)?.file ?? picked.drawingId,
        })}
        pages={v.value.pages}
        credit={v.value.credit ?? null}
        marks={marks}
        tones={tones}
        unit={picked.result.unit}
        focus={focusOf(picked.result)}
      />
    );
  };

  return page(
    <>
      {head()}
      {!drawings.length ? (
        <p className={LINE}>No drawing in this project to check.</p>
      ) : (
        <>
          <Table className="caption-top [overflow-wrap:normal] overflow-hidden rounded-[var(--v-radius)] bg-card text-base shadow-[var(--v-shadow)]">
            {/* inset: the table's rounded, clipped corner would cut the first letter */}
            <TableCaption className="mt-0 px-4 py-3 text-left text-base font-semibold text-foreground">
              Rules: places passed, failed and cannot tell
            </TableCaption>
            <TableHeader className="max-[600px]:hidden">
              <TableRow className="hover:bg-transparent">
                <TableHead scope="col" className="px-4 font-semibold">
                  Rule
                </TableHead>
                <TableHead scope="col" className="px-4 font-semibold">
                  Passed
                </TableHead>
                <TableHead scope="col" className="px-4 font-semibold">
                  Failed
                </TableHead>
                <TableHead scope="col" className="px-4 font-semibold">
                  Cannot tell
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} className="max-[600px]:grid max-[600px]:grid-cols-3">
                  <TableHead
                    scope="row"
                    className="h-auto px-4 py-2.5 font-semibold whitespace-normal max-[600px]:col-span-full [&>small]:block [&>small]:font-normal [&>small]:text-muted-foreground"
                  >
                    {r.title}
                    <small>{r.ref}</small>
                    {r.status === 'not_applicable' && (
                      <small>Does not apply to these drawings</small>
                    )}
                    {r.blind > 0 && (
                      <small>
                        Cannot tell on {plural(r.blind, 'drawing')}: nothing could be read
                      </small>
                    )}
                  </TableHead>
                  <TableCell data-label="Passed" className={CELL}>
                    {r.pass}
                  </TableCell>
                  <TableCell data-label="Failed" className={CELL}>
                    {r.fail}
                  </TableCell>
                  <TableCell data-label="Cannot tell" className={CELL}>
                    {r.cannot_tell}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {clean > 0 && listed.every((x) => !x.results.length) && (
            <p className={LINE}>Every checked place passes these rules.</p>
          )}
        </>
      )}
      <div className="min-w-0">
        {listed.some((x) => x.results.length) && (
          <section aria-labelledby="ck-findings">
            <h2 className="mt-4 mb-2 text-xl" id="ck-findings">
              Findings in your files
            </h2>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {listed.flatMap(({ d, results }) =>
                results.map(({ rule, result }) =>
                  card(d.drawing_id, drawingName(p, d), rule, result),
                ),
              )}
            </ul>
          </section>
        )}
        {clean > 0 && (
          <p className={LINE}>
            {plural(clean, 'drawing')} {clean === 1 ? 'passes' : 'pass'} every checked place
          </p>
        )}
        {none > 0 && (
          <p className={LINE}>
            {plural(none, 'drawing')} {none === 1 ? 'has' : 'have'} nothing these rules apply to
          </p>
        )}
      </div>
      <Dialog
        open={picked !== null}
        onOpenChange={(open) => {
          if (!open) setPicked(null);
        }}
      >
        <DialogContent
          showCloseButton={false}
          aria-describedby={undefined}
          className="ck-viewer flex max-h-[calc(100dvh-32px)] w-[min(1100px,calc(100%-32px))] max-w-none flex-col gap-3 overflow-auto rounded-[20px] border-0 bg-card p-5 text-foreground sm:max-w-none"
        >
          <div className="flex items-center justify-between gap-3">
            <DialogTitle className="min-w-0 text-base font-semibold [overflow-wrap:anywhere]">
              {picked
                ? drawingName(p, {
                    drawing_id: picked.drawingId,
                    file:
                      c.drawings.find((d) => d.drawing_id === picked.drawingId)?.file ??
                      picked.drawingId,
                  })
                : ''}
            </DialogTitle>
            <DialogClose asChild>
              <Button variant="secondary" size="pill" className="v-press font-medium">
                Close
              </Button>
            </DialogClose>
          </div>
          {viewer()}
        </DialogContent>
      </Dialog>
    </>,
  );
}
