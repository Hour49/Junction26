import { useEffect, useRef } from 'react';
import type { Row } from '../api';
import { markWords } from './words';

interface Props {
  row: Row;
  locked: boolean;
  selected: string | null;
  highlighted: string | null;
  onHover: (markId: string | null) => void;
  onEdit: (action: 'reject' | 'restore', markId: string) => void;
}

/** The selected quantity's marks, each with the action that changes it. */
export function MarkList({ row, locked, selected, highlighted, onHover, onEdit }: Props) {
  const items = useRef(new Map<string, HTMLLIElement>());
  useEffect(() => {
    if (selected) items.current.get(selected)?.focus(); // focusing scrolls it into view
  }, [selected]);
  const unknown = row.measure !== 'count' && row.marks.some((m) => m.value === null);
  return (
    <>
      <ol className="sv-marks" aria-label="Marks">
        {row.marks.map((mark) => {
          const words = markWords(mark, row.unit);
          return (
            <li
              key={mark.id}
              tabIndex={-1}
              ref={(el) => {
                if (el) items.current.set(mark.id, el);
                else items.current.delete(mark.id);
              }}
              className={[
                mark.id === highlighted ? 'sv-hot' : '',
                mark.id === selected ? 'sv-sel' : '',
              ]
                .join(' ')
                .trim()}
              onMouseEnter={() => {
                onHover(mark.id);
              }}
              onMouseLeave={() => {
                onHover(null);
              }}
              onFocus={() => {
                onHover(mark.id);
              }}
            >
              <span className="sv-sign">{words.sign}</span>
              <span>{words.text}</span>
              <button
                type="button"
                disabled={locked}
                onClick={() => {
                  onEdit(words.edit, mark.id);
                }}
              >
                {words.action}
              </button>
            </li>
          );
        })}
      </ol>
      {Object.entries(row.unlocated ?? {}).map(([cls, n]) => (
        <p key={cls}>
          + {String(n)} {cls} counted with no mark
        </p>
      ))}
      {unknown && (
        <p>
          A room&apos;s area is unknown, so leaving rooms out does not change the total; settle a
          value instead.
        </p>
      )}
    </>
  );
}
