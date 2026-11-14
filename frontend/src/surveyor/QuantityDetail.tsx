import { useState } from 'react';
import { errorText, formatTime, formatValue, type Edit, type Row } from '../api';
import { MarkList } from './MarkList';
import { statusText } from './words';

interface Props {
  row: Row;
  saving: boolean;
  error: unknown;
  name: string;
  onName: (name: string) => void;
  addMode: boolean;
  onToggleAdd: () => void;
  selectedMark: string | null;
  highlightedMark: string | null;
  onHoverMark: (markId: string | null) => void;
  onEdit: (edit: Edit) => void;
  onSign: (undo: boolean) => void;
}

const LETTERS = 'ABCDEFGHIJ';

function edited(row: Row): boolean {
  return (
    row.status === 'edited' ||
    row.settled !== null ||
    row.marks.some(
      (m) => m.state === 'rejected' || m.state === 'added' || (m.state === 'counted' && m.reason),
    )
  );
}

/** The selected quantity: values, methods, conflict, settle, rule, marks, sign-off. */
export function QuantityDetail(props: Props) {
  const { row, saving, name, onEdit } = props;
  const [typed, setTyped] = useState('');
  const fmt = (v: number) => formatValue(v, row.unit);
  const quantity = row.key;
  const signed = row.signed;
  const locked = saving || signed !== null;
  const settleValue = typed.trim() === '' ? NaN : Number(typed);
  const canSettle = Number.isFinite(settleValue) && settleValue >= 0;
  const conflict = row.conflict;
  const err = props.error === null ? null : errorText(props.error);
  return (
    <section className="sv-detail" aria-label="Selected quantity">
      <h3>
        {row.label} <span className="sv-status">{statusText(row)}</span>
      </h3>
      <p className="sv-value">
        {fmt(row.value)}
        {row.value !== row.original_value && (
          <small> was {fmt(row.original_value)} at ingest</small>
        )}
      </p>
      {row.first && row.second && (
        <p>
          First method: {row.first.method} {fmt(row.first.value)}. Second method:{' '}
          {row.second.method} {fmt(row.second.value)}.
        </p>
      )}
      {conflict && (
        <div className="sv-conflict">
          <ul>
            {conflict.values.map((v, i) => (
              <li key={`${v.method} ${String(i)}`}>
                {LETTERS[i]}: {formatValue(v.value, v.unit ?? row.unit)} {v.method}
              </li>
            ))}
          </ul>
          <p>
            {conflict.resolution
              ? `Kept by rule: ${conflict.resolution.rule} → ${fmt(conflict.resolution.value)}`
              : 'No rule decides. Settle a value before signing off.'}
          </p>
          {conflict.note && <p>{conflict.note}</p>}
          {conflict.derived && <p>{conflict.derived}</p>}
          <div className="sv-tools">
            {conflict.values.map((v, i) => (
              <button
                key={`${v.method} ${String(i)}`}
                type="button"
                disabled={locked}
                onClick={() => {
                  onEdit({ quantity, action: 'settle', value: v.value });
                }}
              >
                Keep {LETTERS[i]}: {fmt(v.value)} ({v.method})
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="sv-tools">
        <label>
          Settle at{' '}
          <input
            type="number"
            min={0}
            step="any"
            value={typed}
            disabled={locked}
            onChange={(e) => {
              setTyped(e.target.value);
            }}
          />
        </label>
        <button
          type="button"
          disabled={locked || !canSettle}
          onClick={() => {
            onEdit({ quantity, action: 'settle', value: settleValue });
          }}
        >
          Settle
        </button>
      </div>
      {row.settled && (
        <p>
          Settled at {fmt(row.settled.value)} ({formatTime(row.settled.at)}). A mark edit clears it.
        </p>
      )}
      {row.estimate && <p>Estimate: {row.estimate}</p>}
      <p>Counting rule: {row.rule.text}</p>
      <MarkList
        row={row}
        locked={locked}
        selected={props.selectedMark}
        highlighted={props.highlightedMark}
        onHover={props.onHoverMark}
        onEdit={(action, mark) => {
          onEdit({ quantity, action, mark });
        }}
      />
      <div className="sv-tools">
        {row.unit === 'count' && (
          <button type="button" disabled={locked} onClick={props.onToggleAdd}>
            {props.addMode
              ? 'Click the missed item on the drawing… (Esc to cancel)'
              : 'Add a missed one'}
          </button>
        )}
        {!signed && edited(row) && (
          <button
            type="button"
            disabled={locked}
            onClick={() => {
              onEdit({ quantity, action: 'reset' });
            }}
          >
            Reset this quantity
          </button>
        )}
      </div>
      {signed && <p>Undo the sign-off to edit.</p>}
      <div className="sv-tools">
        <label>
          Signing as{' '}
          <input
            type="text"
            maxLength={100}
            value={name}
            onChange={(e) => {
              props.onName(e.target.value);
            }}
          />
        </label>
        {signed ? (
          <button
            type="button"
            disabled={saving}
            onClick={() => {
              props.onSign(true);
            }}
          >
            Undo sign-off
          </button>
        ) : (
          <button
            type="button"
            disabled={saving || row.needs_person || name.trim() === ''}
            onClick={() => {
              props.onSign(false);
            }}
          >
            Sign off {fmt(row.value)}
          </button>
        )}
      </div>
      {signed && (
        <p className="sv-signed">
          Signed off by {signed.by}, {formatTime(signed.at)}: {fmt(signed.value)}. Engineers see
          this value as verified.
        </p>
      )}
      {saving && <p role="status">Saving…</p>}
      {err && (
        <div role="alert">
          {err.detail} (code: {err.code})
        </div>
      )}
    </section>
  );
}
