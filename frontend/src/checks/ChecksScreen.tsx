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
  ruleCounts,
  ruleCheckStatus,
  ruleSummary,
  summaryLine,
  viewerMarks,
} from './checks';
import type { CheckResult, ProjectChecks, RuleCheck } from './types';
import './checks.css';

const NOT_DONE = 'The pre-check runs once the drawings are read.';

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
  // Under the list (below 1024 px, checks.css) the viewer is off screen: bring it up, or the tap seems to do nothing.
  const viewerBox = useRef<HTMLElement>(null);
  const showViewer = () => {
    const media = (q: string) =>
      typeof window.matchMedia === 'function' && window.matchMedia(q).matches;
    if (media('(min-width: 1024px)')) return;
    viewerBox.current?.scrollIntoView({
      behavior: media('(prefers-reduced-motion: reduce)') ? 'auto' : 'smooth',
      block: 'start',
    });
  };
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

  const page = (body: JSX.Element) => <div className="v-page ck">{body}</div>;
  if (!pack)
    return page(<p className="ck-line">Choose a country in the header to run its pre-check.</p>);
  if (project.state === 'loading') return page(<Loading label="Loading the checks…" />);
  if (project.state === 'error') return page(<ErrorView error={project.error} />);
  const p = project.value;

  // fail_means says what a fail means for this pack: shown only when a rule failed
  const head = (note: string | null, failed = false) => (
    <header className="ck-head">
      <h1>Pre-check: {rulePack?.name ?? pack}</h1>
      {rulePack && (
        <p className="ck-law">
          {rulePack.country_name} · {rulePack.law}
        </p>
      )}
      {note && (
        <p className="ck-note" role="note">
          {note}
        </p>
      )}
      {failed && rulePack?.fail_means && <p className="ck-law">{rulePack.fail_means}</p>}
    </header>
  );
  const packNote = rulePack?.note ?? null;

  if (!isFinished(p))
    return page(
      <>
        {head(packNote)}
        <p className="ck-line">{NOT_DONE}</p>
        <p className="ck-muted">Project: {PROJECT_STATE_LABEL[p.state] ?? p.state}</p>
      </>,
    );
  if (checks.state === 'loading')
    return page(
      <>
        {head(packNote)}
        <Loading label="Loading the checks…" />
      </>,
    );
  if (checks.state === 'error') {
    const e = checks.error;
    return page(
      <>
        {head(packNote)}
        {notYet(e) ? (
          <p className="ck-line">{NOT_DONE}</p>
        ) : unknownPack(e) ? (
          <p className="ck-line">
            These rules are not available. Pick another country in the header.
          </p>
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
  const withPack = (path: string, q?: string | null) => {
    const query = new URLSearchParams();
    if (q) query.set('q', q);
    query.set('pack', pack);
    return `#${path}?${query.toString()}`;
  };
  const surveyor = (did: string, q?: string | null) =>
    withPack(`/p/${projectId}/d/${did}/surveyor`, q);

  // r null: the rule cannot tell on this drawing without any result (nothing read): its own why, no value or place
  const card = (did: string, rule: RuleCheck, r: CheckResult | null) => {
    const status = r?.status ?? 'cannot_tell';
    const word = STATUS_WORD[status];
    const id = r?.id ?? `rule-${rule.rule_id}`;
    const subject = r && (r.subject.label || `${r.subject.kind} ${r.subject.ref ?? ''}`.trim());
    const located = r !== null && focusOf(r) !== null;
    const isPicked = r !== null && picked?.result.id === r.id && picked.drawingId === did;
    return (
      <li key={`${rule.rule_id}-${id}`}>
        <article
          className={`ck-card ck-${status}`}
          aria-current={isPicked ? 'true' : undefined}
          aria-labelledby={`ck-${did}-${id}`}
        >
          <p className="ck-status">
            <span aria-hidden="true">{word.icon}</span> {word.word}
          </p>
          <h3 id={`ck-${did}-${id}`}>{subject ? `${subject} · ${rule.title}` : rule.title}</h3>
          {r && <p className="ck-value">{limitLine(r)}</p>}
          <p>{r?.why ?? rule.why}</p>
          <div className="ck-clause">
            <p className="ck-ref">{rule.clause.ref}</p>
            <blockquote>{rule.clause.quote}</blockquote>
            {rule.clause.quote_en && rule.clause.quote_en !== rule.clause.quote && (
              <p className="ck-en">{rule.clause.quote_en}</p>
            )}
            <a href={rule.clause.url} target="_blank" rel="noopener noreferrer">
              Read the clause (opens the source)
            </a>
          </div>
          <p className="ck-actions">
            {r && located ? (
              <button
                type="button"
                onClick={() => {
                  setPicked({ key: checksKey, drawingId: did, result: r });
                  loadDrawing(did);
                  showViewer();
                }}
              >
                Show on the drawing
              </button>
            ) : (
              <span className="ck-muted">Not located on the drawing</span>
            )}
            <a href={surveyor(did, r?.quantity)}>Open in the surveyor</a>
          </p>
        </article>
      </li>
    );
  };

  const viewer = () => {
    if (!picked)
      return <p className="ck-muted">Pick “Show on the drawing” on a place to see it here.</p>;
    const v = views.get(picked.drawingId);
    if (!v || v.state === 'loading') return <Loading label="Loading the drawing…" />;
    if (v.state === 'error')
      return (
        <p className="ck-muted">
          Page not available.{' '}
          <button
            type="button"
            onClick={() => {
              loadDrawing(picked.drawingId);
            }}
          >
            Retry
          </button>
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
      {head(c.note || packNote, ruleCounts(rows).failed > 0)}
      {!drawings.length ? (
        <p className="ck-line">No drawing in this project to check.</p>
      ) : (
        <>
          <p className="ck-line">{summaryLine(rows, drawings.length)}</p>
          <table className="ck-table">
            <caption>Rules: places passed, failed and cannot tell</caption>
            <thead>
              <tr>
                <th scope="col">Rule</th>
                <th scope="col">Passed</th>
                <th scope="col">Failed</th>
                <th scope="col">Cannot tell</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row">
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
                  </th>
                  <td data-label="Passed">{r.pass}</td>
                  <td data-label="Failed">{r.fail}</td>
                  <td data-label="Cannot tell">{r.cannot_tell}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {clean > 0 && listed.every((x) => !x.results.length) && (
            <p className="ck-line">Every checked place passes these rules.</p>
          )}
        </>
      )}
      <p className="ck-links">
        <a href={withPack(`/p/${projectId}/issues`)}>Export issues and plans</a>
      </p>
      <div className="ck-split">
        <div className="ck-results">
          {listed
            .filter((x) => x.results.length)
            .map(({ d, results }) => (
              <section key={d.drawing_id} aria-labelledby={`ck-h-${d.drawing_id}`}>
                <h2 id={`ck-h-${d.drawing_id}`}>{drawingName(p, d)}</h2>
                <p className="ck-sub">
                  <a href={surveyor(d.drawing_id)}>Open in the surveyor</a>
                </p>
                <ul className="ck-list" aria-label={`Places to look at in ${drawingName(p, d)}`}>
                  {results.map(({ rule, result }) => card(d.drawing_id, rule, result))}
                </ul>
              </section>
            ))}
          {clean > 0 && (
            <p className="ck-line">
              {plural(clean, 'drawing')} {clean === 1 ? 'passes' : 'pass'} every checked place
            </p>
          )}
          {none > 0 && (
            <p className="ck-line">
              {plural(none, 'drawing')} {none === 1 ? 'has' : 'have'} nothing these rules apply to
            </p>
          )}
        </div>
        {listed.some((x) => x.results.length) && (
          <aside className="ck-viewer" ref={viewerBox}>
            {viewer()}
          </aside>
        )}
      </div>
    </>,
  );
}
