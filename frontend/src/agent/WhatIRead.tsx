import { drawingLabel, formatValue, type ProjectView } from '../api';
import { askable } from '../engineer/projectAsk';
import { kindName } from '../engineer/format';
import { routeLabel } from '../ingest/ingest';

const SHOWN = 3;
const n = (k: number, one: string) => `${String(k)} ${one}${k === 1 ? '' : 's'}`;

/** "5 rooms (52.27 m² indoors) · 2 doors · 2 windows" from a file's takeoff; null when it counted none of them. */
export function readLine(takeoff: Record<string, number> | null | undefined): string | null {
  const t = takeoff ?? {};
  const rooms = t.room ?? 0;
  const indoor = t['area:room|indoor'];
  const parts = [
    rooms > 0 && `${n(rooms, 'room')}${indoor ? ` (${formatValue(indoor, 'm2')} indoors)` : ''}`,
    (t.door ?? 0) > 0 && n(t.door ?? 0, 'door'),
    (t.window ?? 0) > 0 && n(t.window ?? 0, 'window'),
  ].filter((p): p is string => Boolean(p));
  return parts.length ? parts.join(' · ') : null;
}

const sentence = (s: string) =>
  `${s.charAt(0).toUpperCase()}${s.slice(1)}${/[.!?]$/.test(s) ? '' : '.'}`;

/** The empty agent chat's "What I read" (chat-ux #8): per askable drawing its name, kind and route, what the takeoff
 * counted and the server's sentence on how it was read (flags included), from the project alone (no model call). */
export function WhatIRead({ project }: { project: ProjectView }) {
  const drawings = askable(project.drawings);
  if (drawings.length === 0) return null;
  const more = drawings.length - SHOWN;
  return (
    <section className="ag-read" aria-label="What I read">
      <h2 className="en-label">What I read</h2>
      <ul>
        {drawings.slice(0, SHOWN).map((d) => {
          const file = project.files.find((f) => f.drawing_id === d.drawing_id);
          const line = readLine(file?.takeoff);
          return (
            <li key={d.drawing_id}>
              <span>
                <b>{drawingLabel(d)}</b>{' '}
                <span className="en-muted">
                  {kindName(d.kind)} · {routeLabel(d.route)}
                </span>
              </span>
              {line && <span className="ag-read-line">{line}</span>}
              {file?.reason && <span className="ag-read-why">{sentence(file.reason)}</span>}
            </li>
          );
        })}
      </ul>
      {more > 0 && <p className="en-muted">and {n(more, 'more drawing')}</p>}
    </section>
  );
}
