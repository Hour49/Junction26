import { useState } from 'react';
import type { Proposal } from '../agent';
import { checkLine, factLine, pct, shownRuns, type Run, type ServicesChange } from './change';
import './services_change.css';

/** A run as its straight pieces, in percent of the picture (an SVG polyline cannot take percentages, and a
 * stretched viewBox would bend the arrowheads and the round marks). */
function RunLines({ run, className }: { run: Run; className: string }) {
  return (
    <g className={className} data-id={run.id}>
      {run.polyline.slice(1).map((q, i) => {
        const p = run.polyline[i] ?? q;
        return <line key={i} x1={pct(p[0])} y1={pct(p[1])} x2={pct(q[0])} y2={pct(q[1])} />;
      })}
    </g>
  );
}

function Overlay({ c, runs }: { c: ServicesChange; runs: ReturnType<typeof shownRuns> }) {
  return (
    <svg className="sc-overlay" width="100%" height="100%" aria-hidden="true">
      <defs>
        <marker
          id="sc-head"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" className="sc-head" />
        </marker>
      </defs>
      {runs.removed.map((r) => (
        <RunLines key={r.id} run={r} className="sc-removed" />
      ))}
      {runs.added.map((r) => (
        <RunLines key={r.id} run={r} className="sc-added" />
      ))}
      {c.moved.map((m) => (
        <g key={m.id} data-id={m.id}>
          {m.from && m.to && (
            <line
              className="sc-arrow"
              x1={pct(m.from[0])}
              y1={pct(m.from[1])}
              x2={pct(m.to[0])}
              y2={pct(m.to[1])}
              markerEnd="url(#sc-head)"
            />
          )}
          {m.from && <circle className="sc-from" cx={pct(m.from[0])} cy={pct(m.from[1])} r="7" />}
          {m.to && <circle className="sc-to" cx={pct(m.to[0])} cy={pct(m.to[1])} r="5" />}
        </g>
      ))}
    </svg>
  );
}

/** A services proposal on its storey picture (SV-30): the change drawn over it, Before hides it; then the change,
 * the facts and the checks in words. The edit card shows the unknowns, flags and Accept/Reject after it. */
export function ServicesChangePlan({ p }: { p: Proposal }) {
  const [after, setAfter] = useState(true);
  const c = p.services_change;
  if (!c) return null;
  const runs = shownRuns(c);
  const storey = c.storey ?? String(p.page);
  const lines = [
    ...c.moved.map((m) => `Moved: ${m.label}`),
    ...runs.removed.map((r) => `Removed: ${r.label}`),
    ...runs.added.map((r) => `New: ${r.label}`),
  ];
  return (
    <figure className="ag-plan sc-plan" aria-label="Proposed services change">
      <div className="v-segmented ag-toggle" role="group" aria-label="Show the storey">
        {(['Before', 'After'] as const).map((word) => (
          <button
            key={word}
            type="button"
            aria-pressed={after === (word === 'After')}
            onClick={() => {
              setAfter(word === 'After');
            }}
          >
            {word}
          </button>
        ))}
      </div>
      {c.picture ? (
        <div className="ag-planbox">
          <div className="sc-frame">
            <img
              src={c.picture}
              alt={`Services on storey ${storey}, ${after ? 'with the proposed change' : 'as it is'}`}
            />
            {after && <Overlay c={c} runs={runs} />}
          </div>
        </div>
      ) : (
        <p className="en-warn">The storey picture is not available for this change.</p>
      )}
      <figcaption className="ag-legend">
        <span>
          <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
            <line x1="1" y1="7" x2="23" y2="7" className="sc-removed" />
          </svg>
          Removed run (grey, dashed)
        </span>
        <span>
          <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
            <line x1="1" y1="7" x2="23" y2="7" className="sc-added" />
          </svg>
          New run (thick)
        </span>
        <span>
          <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
            <circle cx="6" cy="7" r="5" className="sc-from" />
            <line x1="11" y1="7" x2="22" y2="7" className="sc-arrow" />
          </svg>
          Moved terminal (hollow mark, arrow to its new place)
        </span>
      </figcaption>
      {lines.length > 0 && (
        <ul className="ag-changes" aria-label="Services change">
          {lines.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      {c.facts.length > 0 && (
        <>
          <h4 className="en-label">Before → after</h4>
          <ul className="ag-changes" aria-label="Before → after">
            {c.facts.map((f) => (
              <li key={factLine(f)}>{factLine(f)}</li>
            ))}
          </ul>
        </>
      )}
      {c.checks.length > 0 && (
        <>
          <h4 className="en-label">Checks</h4>
          <ul className="sc-checks" aria-label="Checks">
            {c.checks.map((k) => {
              const { mark, text } = checkLine(k);
              return (
                <li key={k.code} className={k.ok ? 'sc-ok' : 'sc-failed'}>
                  <span aria-hidden="true">{mark}</span>
                  {text}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </figure>
  );
}
