import { useEffect, useRef, useState, type ReactNode } from 'react';
import { pointsOf } from '../agent';
import './multi.css';
import {
  isTerminal,
  laneName,
  markStatus,
  ordered,
  placeOfAction,
  placeOfMark,
  STATUS,
  tabNote,
  type Lane,
  type ServiceAction,
  type ServicesFollow,
  type Status,
} from './services';

const pct = (v: number) => `${String(v * 100)}%`;

/** The discipline's runs and terminals near the edit, over the page (page fractions). Before: as they are.
 * After: each mark in the status of the action that names it, re-seated terminals at their new place, proposed
 * connections dashed. */
function Layer({
  lane,
  after,
  picked,
}: {
  lane: Lane;
  after: boolean;
  picked: ServiceAction | null;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const status = after ? markStatus(lane) : new Map<string, Status>();
  const on = new Set(picked?.refs ?? []);
  const cls = (base: string, ref: string) =>
    `${base}${status.has(ref) ? ` ms--${status.get(ref) ?? ''}` : ''}${on.has(ref) ? ' ms--picked' : ''}`;
  const line = { vectorEffect: 'non-scaling-stroke' } as const;

  // A picked action may be outside the plan box's window: centre it.
  useEffect(() => {
    const box = svg.current?.closest<HTMLElement>('.ag-planbox');
    const at = picked ? placeOfAction(lane, picked) : null;
    if (!box || !at) return;
    box.scrollLeft = at[0] * box.scrollWidth - box.clientWidth / 2;
    box.scrollTop = at[1] * box.scrollHeight - box.clientHeight / 2;
  }, [lane, picked]);

  return (
    <>
      <svg
        ref={svg}
        className="vw-overlay ag-overlay ms-layer"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {lane.marks
          .filter((m) => m.line.length > 1 && on.has(m.ref))
          .map((m) => (
            <polyline key={m.ref} className="ms-halo" points={pointsOf(m.line)} {...line} />
          ))}
        {lane.marks
          .filter((m) => m.line.length > 1)
          .map((m) => (
            <polyline
              key={m.ref}
              className={cls('ms-run', m.ref)}
              points={pointsOf(m.line)}
              {...line}
            />
          ))}
        {after &&
          lane.actions.flatMap((a) =>
            a.paths.map((path, i) => (
              <polyline
                key={`${a.id}-${String(i)}`}
                className="ms-path"
                points={pointsOf(path)}
                {...line}
              />
            )),
          )}
      </svg>
      {lane.marks.map((m) => {
        const at = placeOfMark(m);
        const s = status.get(m.ref);
        const moved = after && lane.actions.some((a) => a.moved_to && a.refs.includes(m.ref));
        // A run is its line; it gets a pin only when an action changes it or asks about it.
        if (!at || (!m.at && (s === undefined || s === 'stays'))) return null;
        return (
          <span
            key={m.ref}
            className={`${cls(isTerminal(m) ? 'ms-dot ms-dot--terminal' : 'ms-dot', m.ref)}${moved ? ' ms-dot--old' : ''}`}
            style={{ left: pct(at[0]), top: pct(at[1]) }}
            title={m.label}
          >
            {s !== undefined && s !== 'stays' && !moved ? STATUS[s].icon : ''}
          </span>
        );
      })}
      {after &&
        lane.actions.map(
          (a) =>
            a.moved_to && (
              <span
                key={a.id}
                className={`ms-dot ms-dot--terminal ms-dot--new ms--follows${picked?.id === a.id ? ' ms--picked' : ''}`}
                style={{ left: pct(a.moved_to[0]), top: pct(a.moved_to[1]) }}
                title="Proposed place"
              >
                {STATUS.follows.icon}
              </span>
            ),
        )}
    </>
  );
}

function Key({ lane, after }: { lane: Lane; after: boolean }) {
  const used = new Set(after ? lane.actions.map((a) => a.status) : []);
  const moved = after && lane.actions.some((a) => a.moved_to);
  const paths = after && lane.actions.some((a) => a.paths.length > 0);
  return (
    <p className="ag-legend ms-key">
      <span>
        <i className="ms-key-run" /> Run
      </span>
      <span>
        <i className="ms-dot ms-dot--terminal" /> Terminal
      </span>
      {(['follows', 'needs_decision', 'cut_off'] as const)
        .filter((s) => used.has(s))
        .map((s) => (
          <span key={s}>
            <i className={`ms-dot ms-dot--terminal ms--${s}`}>{STATUS[s].icon}</i> {STATUS[s].word}
          </span>
        ))}
      {moved && (
        <span>
          <i className="ms-dot ms-dot--terminal ms-dot--old" /> Where it was
        </span>
      )}
      {paths && (
        <span>
          <i className="ms-key-run ms-key-run--path" /> Proposed connection (dashed)
        </span>
      )}
    </p>
  );
}

/** Under the plan: what the discipline's model says about the edit, action by action. */
function Panel({
  services,
  lane,
  after,
  picked,
  onPick,
}: {
  services: ServicesFollow;
  lane: Lane;
  after: boolean;
  picked: ServiceAction | null;
  onPick: (a: ServiceAction | null) => void;
}) {
  const checked = lane.status === 'checked';
  return (
    <section className="ms-panel" aria-label={`${laneName(lane)} after the change`}>
      {checked && lane.marks.length > 0 && <Key lane={lane} after={after} />}
      <p className="ms-line">{lane.line}</p>
      {checked && (
        <p className="en-small">
          {String(lane.elements)} elements of {lane.source ?? 'the model'}
          {services.storey ? ` on storey ${services.storey}` : ''}; the plan shows the ones near the
          change.
        </p>
      )}
      {lane.actions.length > 0 && (
        <ul className="ms-actions">
          {ordered(lane.actions).map((a) => {
            const shown = placeOfAction(lane, a) !== null;
            return (
              <li key={a.id} className={`ag-law-row ms-action ms-action--${a.status}`}>
                <p className="ms-status">
                  <span aria-hidden="true">{STATUS[a.status].icon}</span> {STATUS[a.status].word}
                  {a.system ? <span className="ms-system"> · {a.system}</span> : null}
                </p>
                <p>{a.label}</p>
                {shown && (
                  <button
                    type="button"
                    className="ag-law-subject ag-law-pick"
                    aria-pressed={picked?.id === a.id}
                    onClick={() => {
                      onPick(picked?.id === a.id ? null : a);
                    }}
                  >
                    Show on the plan
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {checked && services.unknowns.length > 0 && (
        <>
          <h4 className="en-label">Not checked</h4>
          <ul className="ag-unknowns">
            {services.unknowns.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </>
      )}
      {services.credits.map((c) => (
        <p key={c} className="en-small">
          {c}
        </p>
      ))}
    </section>
  );
}

/** The edit card's discipline tabs: `Plan` and one per service discipline. A discipline tab draws that model's
 * runs and terminals near the change over the plan (with Before / After) and lists what the change does to them.
 * Null when the proposal carries no follow-up (SERVICES_FOLLOW off). The three parts go where the card has its
 * toggle, its page overlay and the foot of its plan. */
export function useServiceTabs(
  services: ServicesFollow | null | undefined,
  after: boolean,
): { tabs: ReactNode; layer: ReactNode; panel: ReactNode } | null {
  const [name, setName] = useState<string | null>(null);
  const [pickedId, setPickedId] = useState<string | null>(null);
  if (!services) return null;
  const lane = services.disciplines.find((l) => l.discipline === name) ?? null;
  const picked = lane?.actions.find((a) => a.id === pickedId) ?? null;
  const open = (next: string | null) => {
    setName(next);
    setPickedId(null);
  };
  return {
    tabs: (
      <div className="v-segmented ms-tabs" role="group" aria-label="Discipline">
        <button
          type="button"
          aria-pressed={lane === null}
          onClick={() => {
            open(null);
          }}
        >
          Plan
        </button>
        {services.disciplines.map((l) => {
          const note = tabNote(l);
          return (
            <button
              key={l.discipline}
              type="button"
              aria-pressed={lane === l}
              onClick={() => {
                open(l.discipline);
              }}
            >
              {laneName(l)}
              {note !== null && (
                <span className={l.status === 'checked' ? 'ms-count' : 'ms-off'}>{note}</span>
              )}
            </button>
          );
        })}
      </div>
    ),
    layer: lane && <Layer lane={lane} after={after} picked={picked} />,
    panel: lane && (
      <Panel
        services={services}
        lane={lane}
        after={after}
        picked={picked}
        onPick={(a) => {
          setPickedId(a?.id ?? null);
        }}
      />
    ),
  };
}
