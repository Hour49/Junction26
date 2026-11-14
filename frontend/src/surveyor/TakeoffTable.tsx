import { formatValue, type Row, type Takeoff } from '../api';
import { statusText } from './words';

interface Props {
  takeoff: Takeoff;
  selected: string | null;
  onSelect: (key: string) => void;
}

function Rows({ rows, selected, onSelect }: { rows: Row[] } & Omit<Props, 'takeoff'>) {
  return rows.map((row) => (
    <tr key={row.key} data-key={row.key} aria-current={row.key === selected ? 'true' : undefined}>
      <th scope="row">
        <button
          type="button"
          onClick={() => {
            onSelect(row.key);
          }}
        >
          {row.label}
        </button>
        {row.first && row.second && (
          <small>
            {row.first.method} {formatValue(row.first.value, row.unit)} · {row.second.method}{' '}
            {formatValue(row.second.value, row.unit)}
          </small>
        )}
      </th>
      <td className="sv-num">
        {row.value !== row.original_value && (
          <>
            <s>{formatValue(row.original_value, row.unit)}</s>{' '}
          </>
        )}
        {formatValue(row.value, row.unit)}
      </td>
      <td>{statusText(row)}</td>
    </tr>
  ));
}

/** The takeoff: the review queue first, in its order, then every other row in takeoff order. */
export function TakeoffTable({ takeoff, selected, onSelect }: Props) {
  const byKey = new Map(takeoff.quantities.map((q) => [q.key, q]));
  const queue = takeoff.review_queue.flatMap((key) => byKey.get(key) ?? []);
  const rest = takeoff.quantities.filter((q) => !queue.includes(q));
  const head = (
    <thead>
      <tr>
        <th scope="col">Quantity</th>
        <th scope="col">Value</th>
        <th scope="col">State</th>
      </tr>
    </thead>
  );
  return (
    <div className="sv-tables">
      <table className="sv-table">
        <caption>To review</caption>
        {head}
        <tbody>
          {queue.length ? (
            <Rows rows={queue} selected={selected} onSelect={onSelect} />
          ) : (
            <tr>
              <td colSpan={3}>Nothing left to review.</td>
            </tr>
          )}
        </tbody>
      </table>
      <table className="sv-table">
        <caption>All other quantities</caption>
        {head}
        <tbody>
          <Rows rows={rest} selected={selected} onSelect={onSelect} />
        </tbody>
      </table>
    </div>
  );
}
