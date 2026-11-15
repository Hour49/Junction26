import { useEffect, useRef, useState, type ReactNode } from 'react';
import { pointsOf, type Box, type Proposal } from '../agent';
import './multi.css';
import {
  focusOf,
  isTerminal,
  laneName,
  markStatus,
  onSheet,
  ordered,
  PAIRED_BY,
  pictureOf,
  placeOfAction,
  placeOfMark,
  STATUS,
  strikeOf,
  tabNote,
  type Lane,
  type LanePicture,
  type ServiceAction,
  type ServicesFollow,
  type Status,
} from './services';

const pct = (v: number) => `${String(v * 100)}%`;
const ALL = ' all'; // the All sheets view's tab name: no discipline is spelled so

/** AC-45: one lane's sheet in the All sheets view: where it is, what to zoom to, what to draw on it. */
export interface SyncSheet {
  discipline: string;
  name: string;
  sheet: { drawing_id: string; page: number };
  focus: Box | null;
  layer: ReactNode;
  open: () => void;
}

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

/** AC-40: the edit on the lane's own sheet, in that sheet's page fractions: the removed strip struck out, the new
 * partition drawn (the plan's Demolished and New looks). Before shows none of it. */
function SheetEdit({ pic }: { pic: LanePicture }) {
  const line = { vectorEffect: 'non-scaling-stroke' } as const;
  return (
    <svg
      className="vw-overlay ag-overlay"
      viewBox="0 0 1 1"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {pic.removed.map((strip, i) => {
        const strike = strikeOf(strip);
        return (
          <g key={`r${String(i)}`}>
            <polygon className="ag-removed" points={pointsOf(strip)} {...line} />
            {strike && <polyline className="ag-strike" points={pointsOf(strike)} {...line} />}
          </g>
        );
      })}
      {pic.added.map((wall, i) => (
        <polygon key={`a${String(i)}`} className="ag-added" points={pointsOf(wall)} {...line} />
      ))}
    </svg>
  );
}

/** The part of the sheet to look at: the edit's own outlines there plus a margin, else (no outline on the
 * sheet) the lane's focus. Not every mark's: a picture's lane carries every symbol its reader found on the sheet
 * (562 on DigitalHub's P-101), and their box was nearly the whole sheet, the struck-out wall cut off at its edge
 * (R1 edits 10c). What sits on the wall is inside the margin. */
export function sheetFocus(lane: Lane, pic: LanePicture): Box | null {
  const pts = [...pic.removed, ...pic.added].flat();
  if (pts.length === 0) {
    const edit = { removed: [], added: [] };
    return focusOf(onSheet(lane, pic), edit);
  }
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const [x0, y0, x1, y1] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  const pad = Math.max(0.05, 0.5 * Math.max(x1 - x0, y1 - y0));
  return [x0 - pad, y0 - pad, x1 + pad, y1 + pad];
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
 * toggle, its page overlay and the foot of its plan; `focus` is the part of the page the open tab draws on, for
 * the card to zoom to. */
export function useServiceTabs(
  p: Proposal,
  after: boolean,
): {
  tabs: ReactNode;
  head: ReactNode;
  layer: ReactNode;
  panel: ReactNode;
  focus: Box | null;
  /** AC-40: the open lane's own services sheet, drawn instead of the plan; null: the plan. */
  sheet: { drawing_id: string; page: number } | null;
  /** AC-45: All sheets: each lane's picture with the edit on it, for the card to show beside the plan; null: one
   * view (the card's plan box). */
  sync: SyncSheet[] | null;
} | null {
  const [name, setName] = useState<string | null>(null);
  const [pickedId, setPickedId] = useState<string | null>(null);
  // AC-43: the lanes whose sheet the user said is not this floor's (kept in the card)
  const [refused, setRefused] = useState<ReadonlySet<string>>(new Set());
  const services = p.services;
  if (!services) return null;
  // AC-45: the lanes with a picture of their own the user has not refused, for All sheets
  const pictured = services.disciplines.flatMap((l) => {
    const own = refused.has(l.discipline) ? null : pictureOf(l);
    return own ? [{ lane: l, pic: own }] : [];
  });
  const all = name === ALL && pictured.length > 0;
  const lane = all ? null : (services.disciplines.find((l) => l.discipline === name) ?? null);
  const picked = lane?.actions.find((a) => a.id === pickedId) ?? null;
  const said = lane !== null && refused.has(lane.discipline);
  const pic = lane && !said ? pictureOf(lane) : null;
  const refuse = (discipline: string, no: boolean) => {
    const next = new Set(refused);
    if (no) next.add(discipline);
    else next.delete(discipline);
    setRefused(next);
    setPickedId(null);
  };
  const open = (next: string | null) => {
    setName(next);
    setPickedId(null);
  };
  return {
    tabs: (
      <div className="v-segmented ms-tabs" role="group" aria-label="Discipline">
        <button
          type="button"
          aria-pressed={lane === null && !all}
          onClick={() => {
            open(null);
          }}
        >
          Plan
        </button>
        {pictured.length > 0 && (
          <button
            type="button"
            aria-pressed={all}
            onClick={() => {
              open(ALL);
            }}
          >
            All sheets
          </button>
        )}
        {services.disciplines.map((l) => {
          const off = refused.has(l.discipline);
          const note = off ? 'not checked' : tabNote(l);
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
                <span className={l.status === 'checked' && !off ? 'ms-count' : 'ms-off'}>
                  {note}
                </span>
              )}
            </button>
          );
        })}
      </div>
    ),
    sheet: pic && { drawing_id: pic.drawing_id, page: pic.page },
    sync: all
      ? pictured.map(({ lane: l, pic: own }) => ({
          discipline: l.discipline,
          name: laneName(l),
          sheet: { drawing_id: own.drawing_id, page: own.page },
          focus: sheetFocus(l, own),
          layer: (
            <>
              {after && <SheetEdit pic={own} />}
              <Layer lane={onSheet(l, own)} after={after} picked={null} />
            </>
          ),
          open: () => {
            open(l.discipline);
          },
        }))
      : null,
    head: lane && (pic || said) && (
      <p className="ms-pairing">
        {pic ? (
          <span>
            {PAIRED_BY[pic.pairing.paired_by]}: {pic.pairing.reason}
          </span>
        ) : (
          <span>Not checked: you said this is not this floor&apos;s {lane.discipline} sheet.</span>
        )}
        <button
          type="button"
          className="ag-law-subject"
          onClick={() => {
            refuse(lane.discipline, !said);
          }}
        >
          {said ? 'Use this sheet again' : 'Not this sheet'}
        </button>
      </p>
    ),
    focus: lane && !said ? (pic ? sheetFocus(lane, pic) : focusOf(lane, p)) : null,
    layer:
      lane &&
      !said &&
      (pic ? (
        <>
          {after && <SheetEdit pic={pic} />}
          <Layer lane={onSheet(lane, pic)} after={after} picked={picked} />
        </>
      ) : (
        <Layer lane={lane} after={after} picked={picked} />
      )),
    panel: lane && !said && (
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
