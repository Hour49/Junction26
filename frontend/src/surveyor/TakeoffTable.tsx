import { useEffect, useState } from 'react';
import { Tip } from '@/components/ui/tip';
import { REVIEW_TIPS } from '../shell/tips-review';
import {
  formatValue,
  methodName,
  pickInUse,
  resolverModel,
  resolverName,
  type Row,
  type Takeoff,
} from '../api';
import { statusText } from './words';
import { Button } from '@/components/ui/button';
import { ROW } from './ui';

interface Props {
  takeoff: Takeoff;
  selected: string | null;
  onSelect: (key: string) => void;
}

const PHONE = '(max-width: 640px)'; // surveyor.css's card layout

/** Whether the window is phone-wide (PHONE), following resizes; false where matchMedia is missing. */
function usePhone(): boolean {
  const [phone, setPhone] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE).matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia(PHONE);
    const follow = () => {
      setPhone(query.matches);
    };
    query.addEventListener('change', follow);
    return () => {
      query.removeEventListener('change', follow);
    };
  }, []);
  return phone;
}

/** R3-G9: on a phone the cards that need the surveyor come first (a person's call, then a conflict); stable. */
const rank = (row: Row) => (row.needs_person ? 0 : row.conflict ? 1 : 2);
const needsFirst = (rows: Row[]) => [...rows].sort((a, b) => rank(a) - rank(b));

function Rows({ rows, selected, onSelect }: { rows: Row[] } & Omit<Props, 'takeoff'>) {
  return rows.map((row) => (
    <tr key={row.key} data-key={row.key} aria-current={row.key === selected ? 'true' : undefined}>
      <th scope="row">
        <Button
          variant="ghost"
          className={ROW}
          onClick={() => {
            onSelect(row.key);
          }}
        >
          {row.label}
        </Button>
        {row.first && row.second && (
          <small>
            {methodName(row.first.method)} {formatValue(row.first.value, row.unit)} ·{' '}
            {methodName(row.second.method)} {formatValue(row.second.value, row.unit)}
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
      <td>
        {pickInUse(row) && row.resolved ? (
          // a model's pick in use (#252 RS-15): its name, the model id only in the tooltip
          <span className="sv-status" data-status="picked" title={resolverModel(row.resolved.by)}>
            Picked by {resolverName(row.resolved.by)}
          </span>
        ) : (
          <span className="sv-status" data-status={row.needs_person ? 'needs' : row.status}>
            {statusText(row)}
          </span>
        )}
      </td>
    </tr>
  ));
}

/** The takeoff: the review queue first, in its order, then every other row in takeoff order. */
export function TakeoffTable({ takeoff, selected, onSelect }: Props) {
  const byKey = new Map(takeoff.quantities.map((q) => [q.key, q]));
  const queue = takeoff.review_queue.flatMap((key) => byKey.get(key) ?? []);
  const rest = takeoff.quantities.filter((q) => !queue.includes(q));
  const phone = usePhone();
  const order = phone ? needsFirst : (rows: Row[]) => rows;
  const head = (
    <thead>
      <tr>
        <th scope="col">
          <Tip text={REVIEW_TIPS.colQuantity} wrap>
            <span>Quantity</span>
          </Tip>
        </th>
        <th scope="col">
          <Tip text={REVIEW_TIPS.colValue} wrap>
            <span>Value</span>
          </Tip>
        </th>
        <th scope="col">
          <Tip text={REVIEW_TIPS.colState} wrap>
            <span>State</span>
          </Tip>
        </th>
      </tr>
    </thead>
  );
  return (
    <>
      <table className="sv-table">
        <caption>
          <Tip text={REVIEW_TIPS.toReview} wrap>
            <span>To review</span>
          </Tip>
        </caption>
        {head}
        <tbody>
          {queue.length ? (
            <Rows rows={order(queue)} selected={selected} onSelect={onSelect} />
          ) : (
            <tr>
              <td colSpan={3}>Nothing left to review.</td>
            </tr>
          )}
        </tbody>
      </table>
      <table className="sv-table">
        <caption>
          <Tip text={REVIEW_TIPS.allOther} wrap>
            <span>All other quantities</span>
          </Tip>
        </caption>
        {head}
        <tbody>
          <Rows rows={order(rest)} selected={selected} onSelect={onSelect} />
        </tbody>
      </table>
    </>
  );
}
