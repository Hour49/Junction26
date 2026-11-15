import { useState, type CSSProperties } from 'react';
import type { Point, Proposal } from '../agent';
import {
  checkLine,
  factLine,
  pct,
  shownRuns,
  zoomBox,
  type Run,
  type ServicesChange,
} from './change';
import './services_change.css';

type Box = ReturnType<typeof zoomBox>;
const WHOLE: Box = { x: 0, y: 0, s: 1 };

/** A page place as a place on the picture as shown (the close-up or the whole page). */
const shown = (b: Box) => (p: Point) => [(p[0] - b.x) / b.s, (p[1] - b.y) / b.s] as const;

/** A run as its straight pieces, in percent of the picture (an SVG polyline cannot take percentages, and a
 * stretched viewBox would bend the arrowheads and the round marks). */
function RunLines({
  run,
  className,
  at,
}: {
  run: Run;
  className: string;
  at: ReturnType<typeof shown>;
}) {
  return (
    <g className={className} data-id={run.id}>
      {run.polyline.slice(1).map((q, i) => {
        const [x1, y1] = at(run.polyline[i] ?? q);
        const [x2, y2] = at(q);
        // a new run's pathLength 1: the CSS draws it on along its length (dash offset 1 to 0); not on a removed
        // run, whose 6 4 dashes pathLength would stretch into one solid line
        const draw = className === 'sc-added' ? 1 : undefined;
        return (
          <line key={i} x1={pct(x1)} y1={pct(y1)} x2={pct(x2)} y2={pct(y2)} pathLength={draw} />
        );
      })}
    </g>
  );
}

function Overlay({
  c,
  runs,
  box,
}: {
  c: ServicesChange;
  runs: ReturnType<typeof shownRuns>;
  box: Box;
}) {
  const at = shown(box);
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
        <RunLines key={r.id} run={r} className="sc-removed" at={at} />
      ))}
      {runs.added.map((r) => (
        <RunLines key={r.id} run={r} className="sc-added" at={at} />
      ))}
      {c.moved.map((m) => {
        const from = m.from ? at(m.from) : null;
        const to = m.to ? at(m.to) : null;
        // the new mark slides in from the old place (CSS, only without reduced motion)
        const slide = (
          from && to ? { '--dx': pct(from[0] - to[0]), '--dy': pct(from[1] - to[1]) } : {}
        ) as CSSProperties;
        return (
          <g key={m.id} data-id={m.id}>
            {from && to && (
              <line
                className="sc-arrow"
                x1={pct(from[0])}
                y1={pct(from[1])}
                x2={pct(to[0])}
                y2={pct(to[1])}
                markerEnd="url(#sc-head)"
              />
            )}
            {from && <circle className="sc-from" cx={pct(from[0])} cy={pct(from[1])} r="7" />}
            {to && (
              <>
                <circle className="sc-ring" cx={pct(to[0])} cy={pct(to[1])} r="11" />
                <circle className="sc-to" cx={pct(to[0])} cy={pct(to[1])} r="6" style={slide} />
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** A services proposal on its storey picture (SV-30): the change drawn over it, Before hides it; then the change,
 * the facts and the checks in words. The edit card shows the unknowns, flags and Accept/Reject after it. */
export function ServicesChangePlan({ p }: { p: Proposal }) {
  const [after, setAfter] = useState(true);
  const [whole, setWhole] = useState(false);
  const c = p.services_change;
  if (!c) return null;
  const runs = shownRuns(c);
  const close = zoomBox(c, runs);
  const box = whole || close.s >= 1 ? WHOLE : close;
  const r = (v: number) => Math.round(v * 10000) / 100; // a fraction as a percent, 2 decimals
  const storey = c.storey ?? String(p.page);
  const lines = [
    ...c.moved.map((m) => `Moved: ${m.label}`),
    ...runs.removed.map((r) => `Removed: ${r.label}`),
    ...runs.added.map((r) => `New: ${r.label}`),
  ];
  return (
    <figure className="ag-plan sc-plan" aria-label="Proposed services change">
      <div className="sc-toggles">
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
        {close.s < 1 && (
          <div className="v-segmented ag-toggle" role="group" aria-label="Picture">
            {(['Close-up', 'Whole floor'] as const).map((word) => (
              <button
                key={word}
                type="button"
                aria-pressed={whole === (word === 'Whole floor')}
                onClick={() => {
                  setWhole(word === 'Whole floor');
                }}
              >
                {word}
              </button>
            ))}
          </div>
        )}
      </div>
      {c.picture ? (
        <div className="ag-planbox">
          <div className="sc-frame">
            <img
              src={c.picture}
              alt={`Services on storey ${storey}, ${after ? 'with the proposed change' : 'as it is'}${
                box === WHOLE ? '' : ', close up'
              }`}
              style={
                box === WHOLE
                  ? undefined
                  : {
                      transform: `scale(${String(r(1 / box.s) / 100)}) translate(${String(-r(box.x))}%, ${String(-r(box.y))}%)`,
                    }
              }
            />
            {after && <Overlay c={c} runs={runs} box={box} />}
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
          New run (accent, thick)
        </span>
        <span>
          <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
            <circle cx="6" cy="7" r="5" className="sc-from" />
            <line x1="11" y1="7" x2="22" y2="7" className="sc-arrow" />
          </svg>
          Moved terminal (hollow mark, arrow to its new place)
        </span>
        <span>
          <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
            <circle cx="12" cy="7" r="6" className="sc-ring" />
            <circle cx="12" cy="7" r="3" className="sc-to" />
          </svg>
          New place (filled mark with a ring)
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
