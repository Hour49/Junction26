import { useEffect, useId, useState } from 'react';
import { ApiError, errorText, getProjectChecks, rulePacksOf, type ProjectChecks } from '../api';
import { useInfo } from '../shell/info';
import { routeHref } from '../shell/route';
import { countParts, ruleCounts } from './conflicts';

// `key` = the request it answers, so a new pack or a Retry shows loading without a reset in the effect
type Load = { key: string } & ({ checks: ProjectChecks } | { error: unknown });

/** The conflicts screen's building-code row (conflicts.md "Checks row"); shown only with a pack. */
export function ChecksRow({ projectId, pack }: { projectId: string; pack: string }) {
  const id = useId();
  const [answer, setAnswer] = useState<Load | null>(null);
  const [attempt, setAttempt] = useState(0);
  const name = rulePacksOf(useInfo().info).find((p) => p.id === pack)?.name ?? pack;

  useEffect(() => {
    const abort = new AbortController();
    const key = `${pack} ${String(attempt)}`;
    getProjectChecks(projectId, { pack, signal: abort.signal }).then(
      (checks) => {
        setAnswer({ key, checks });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setAnswer({ key, error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, pack, attempt]);

  const load = answer?.key === `${pack} ${String(attempt)}` ? answer : null;
  let body;
  if (load === null) body = <p role="status">Checking against {name}…</p>;
  else if ('error' in load) {
    const e = load.error;
    if (e instanceof ApiError && e.status === 409)
      body = <p>The checks run when reading is done.</p>;
    else if (e instanceof ApiError && e.code === 'unknown_pack')
      body = <p>These rules are not available. Pick another country.</p>;
    else
      body = (
        <div role="alert" className="cf-error">
          {errorText(e).detail}{' '}
          <button
            type="button"
            className="cf-btn"
            onClick={() => {
              setAttempt((n) => n + 1);
            }}
          >
            Retry
          </button>
        </div>
      );
  } else {
    const parts = countParts(ruleCounts(load.checks));
    body = (
      <>
        {parts.length === 0 ? (
          <p>Nothing on these drawings that these rules check.</p>
        ) : (
          <p className="cf-checks-counts">
            {parts.map((p, i) => (
              <span key={p.kind}>
                {i > 0 && ' · '}
                <span className={`cf-pill cf-check-${p.kind}`}>{p.text}</span>
              </span>
            ))}
          </p>
        )}
        <p className="cf-checks-note">{load.checks.note}</p>
        <a
          className="cf-quiet"
          href={routeHref({ name: 'checks', projectId, query: new URLSearchParams({ pack }) })}
        >
          See the checks
        </a>
      </>
    );
  }
  return (
    <section className="cf-checks" aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`} className="cf-checks-title">
        Building-code pre-check: {name}
      </h2>
      {body}
    </section>
  );
}
