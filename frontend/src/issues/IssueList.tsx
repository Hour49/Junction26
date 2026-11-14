import type { Issue } from '../api';
import {
  SEVERITIES,
  SEVERITY_LABEL,
  STATE_LABEL,
  kindOf,
  placeOf,
  routeOf,
  type Row,
} from './issues';

/** A failed rule's clause, when the issue's `check` carries one (shape pending record 0008). */
function clauseOf(
  check: Issue['check'],
): { ref: string; quote: string; url: string | null } | null {
  const ref = check?.ref;
  const quote = check?.quote;
  if (typeof ref !== 'string' || typeof quote !== 'string') return null;
  return { ref, quote, url: typeof check?.url === 'string' ? check.url : null };
}

const TONE = { fails_rule: 'v-pill--danger', needs_person: 'v-pill--warn', note: '' } as const;

/** The issues under their severity headings, in the API's order; each row selects, its links settle. */
export function IssueList({
  rows,
  selected,
  projectId,
  pack,
  onSelect,
}: {
  rows: Row[];
  selected: string | null;
  projectId: string;
  pack: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <>
      {SEVERITIES.map((severity) => {
        const here = rows.filter((r) => r.issue.severity === severity);
        if (here.length === 0) return null;
        const heading = SEVERITY_LABEL[severity];
        return (
          <section key={severity} aria-label={heading} className="is-group">
            <h2 className="v-h3">{heading}</h2>
            <ul className="v-card is-list">
              {here.map(({ issue, n }) => {
                const kind = kindOf(issue.kind);
                const state = STATE_LABEL[issue.state];
                const clause = clauseOf(issue.check);
                return (
                  <li
                    key={issue.id}
                    id={`issue-${issue.id}`}
                    className="is-row"
                    aria-current={issue.id === selected ? 'true' : undefined}
                  >
                    <button
                      type="button"
                      className="is-pick"
                      onClick={() => {
                        onSelect(issue.id);
                      }}
                    >
                      <span className="is-n">{n}</span>
                      <span className="is-body">
                        <span className={`v-pill is-kind ${TONE[severity]}`}>
                          {kind.icon && <span aria-hidden="true">{kind.icon} </span>}
                          {kind.word}
                        </span>
                        <span className="is-why">{issue.why}</span>
                        <span className="is-place">{placeOf(issue)}</span>
                      </span>
                      <span className="is-state">
                        <span aria-hidden="true">{state.icon} </span>
                        {state.word}
                      </span>
                    </button>
                    {issue.question && <p className="is-more">Asked: {issue.question}</p>}
                    {issue.reason && issue.reason !== issue.why && (
                      <p className="is-more">{issue.reason}</p>
                    )}
                    {clause && (
                      <p className="is-more">
                        {clause.url ? <a href={clause.url}>{clause.ref}</a> : clause.ref}: “
                        {clause.quote}”
                      </p>
                    )}
                    <p className="is-links">
                      {routeOf(issue, projectId, pack).map((l) => (
                        <a key={l.label} href={l.href}>
                          {l.label}
                        </a>
                      ))}
                    </p>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </>
  );
}
