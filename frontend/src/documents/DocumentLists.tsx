import { drawingLabel, type ProjectView, type Triage } from '../api';
import { formatSize, isFinished, kindLabel, plural, routeLabel } from '../ingest/ingest';
import { StateBadge } from '../ingest/ProjectScreen';
import { isNotPlan, looksLike, rowLine, verdictOf } from '../ingest/triage';
import { shortReason } from './documents';

/** A triaged non-plan's row line (file-triage.md flow 1): class, subject, verdict pill, whose call. */
function TriageLine({ triage }: { triage: Triage }) {
  return (
    <span className="reason">
      {rowLine(triage)}{' '}
      <span className={`v-pill${triage.verdict === 'unsure' ? ' v-pill--warn' : ''}`}>
        {verdictOf(triage).pill}
      </span>
      {triage.overruled && ` · ${triage.overruled.by}’s call`}
    </span>
  );
}

/** Documents' drawings and files (documents.md flow 5-6), moved from the Ingest screen. */
export function DocumentLists({ project }: { project: ProjectView }) {
  const base = `#/p/${project.id}`;
  const live = !project.files.every(isFinished) || project.state === 'queued';
  return (
    <>
      <section aria-label="Drawings" className="doc-section">
        <h2 className="doc-h">Drawings</h2>
        {project.drawings.length === 0 ? (
          <p className="doc-muted">
            {live
              ? 'No drawing ready yet.'
              : 'No drawings: nothing in this upload could be read as a plan.'}
          </p>
        ) : (
          <ul className="doc-dwgs">
            {project.drawings.map((d) => (
              <li key={d.drawing_id} className="v-card doc-dwg">
                <b>{drawingLabel(d)}</b>
                <span className="doc-small doc-mono">{d.file}</span>
                <span className="doc-small">
                  {kindLabel(d.kind)}
                  {d.route && ` · ${routeLabel(d.route)}`}
                </span>
                <a
                  className="v-btn v-btn--secondary v-press"
                  href={`${base}/d/${d.drawing_id}/engineer`}
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-label="Files" className="doc-section">
        <h2 className="doc-h">Files</h2>
        {typeof project.not_plans === 'number' && (
          <p className="doc-small">
            {project.not_plans === 0
              ? 'No image set aside as not a floor plan'
              : `${plural(project.not_plans, 'not a floor plan', 'not floor plans')}: kept, not read`}
          </p>
        )}
        {project.files.length === 0 ? (
          <p className="doc-muted">
            {live ? 'Waiting for the files…' : 'This upload has no files.'}
          </p>
        ) : (
          <ul className="v-card doc-files">
            {project.files.map((f) => (
              <li key={f.id}>
                <a className="doc-file v-press" href={`${base}/f/${f.id}`}>
                  <span className="doc-file-main">
                    <span className="doc-mono">{f.path}</span>
                    {f.triage?.read_as_plan ? (
                      <span className="reason">
                        Read as a floor plan on {f.triage.read_as_plan.by}’s call
                      </span>
                    ) : f.triage && isNotPlan(f) ? (
                      <TriageLine triage={f.triage} />
                    ) : f.triage && looksLike(f.triage) ? (
                      <span className="reason">{rowLine(f.triage)}</span>
                    ) : (
                      shortReason(f) && <span className="reason">{shortReason(f)}</span>
                    )}
                  </span>
                  <span className="doc-file-meta">
                    <StateBadge state={f.state} />
                    <span className="doc-small">
                      {kindLabel(f.kind)} · {formatSize(f.size)}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
