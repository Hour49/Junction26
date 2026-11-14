import { formatTime, formatValue, methodName, type Row } from '../api';

/** The row's review state in words (the status is the pill beside it): the second method or the conflict, estimate, edits. */
export function ChecksPanel({ row }: { row: Row }) {
  const { conflict, first, second, settled } = row;
  const value = (v: number) => formatValue(v, row.unit);
  return (
    <div className="en-checks">
      {conflict ? (
        <>
          <ul className="en-conflict">
            {conflict.values.map((v, i) => (
              <li key={i}>
                {formatValue(v.value, v.unit ?? row.unit)} by {methodName(v.method)}
              </li>
            ))}
          </ul>
          {/* A settled value replaces the rule's choice: the settled line says it. */}
          {settled ? null : conflict.resolution ? (
            <p>
              Kept {value(conflict.resolution.value)}: {conflict.resolution.rule}
            </p>
          ) : (
            row.needs_person && (
              <p className="en-warn">
                No rule decides. A surveyor has to settle it before this value can be used.
              </p>
            )
          )}
        </>
      ) : first && second ? (
        <p>
          Second method ({methodName(second.method)}): {value(second.value)}, agrees
        </p>
      ) : (
        <p>{row.estimate ? 'Estimated' : 'Measured'} by one method; no second check.</p>
      )}
      {row.estimate && <p className="en-warn">Estimate: {row.estimate}</p>}
      {settled && (
        <p>
          Settled by a surveyor at {formatTime(settled.at)}: {value(settled.value)}
        </p>
      )}
      {row.value !== row.original_value && (
        <p>Changed in review, was {value(row.original_value)}</p>
      )}
    </div>
  );
}
