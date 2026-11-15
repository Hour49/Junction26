import { formatValue, type MarkView, type Row } from '../api';

// engineer.md EN-31's words, so a status reads the same on both screens.
const STATUS: Record<Row['status'], string> = {
  signed: 'Verified',
  conflict: 'Methods disagree',
  estimate: 'Estimate',
  edited: 'Changed in review',
  agree: 'Two methods agree',
  single: 'One method',
};

type StatusRow = Pick<Row, 'status' | 'needs_person'> &
  Partial<Pick<Row, 'conflict' | 'settled' | 'value' | 'original_value'>>;

export function statusText(row: StatusRow): string {
  if (row.needs_person) return `${STATUS[row.status]} · needs you`;
  // R4-B11: a conflict a rule decided reads as the project page's card does, not as an open disagreement
  if (row.status === 'conflict' && row.conflict?.resolution && !row.settled)
    return 'Settled by a rule';
  // R4-B5: settled at the value it already had: nothing changed
  if (row.status === 'edited' && row.settled && row.value === row.original_value)
    return 'Settled by you';
  return STATUS[row.status];
}

export interface MarkWords {
  sign: string;
  text: string;
  action: string;
  edit: 'reject' | 'restore';
}

/** How one mark row reads: its sign, its words, and the action that changes it. */
export function markWords(mark: MarkView, unit: string): MarkWords {
  const count = unit === 'count';
  const label = mark.label ?? 'item';
  const sign = mark.n === null ? '' : String(mark.n);
  switch (mark.state) {
    case 'rejected':
      return {
        sign: '×',
        text: `${label}, ${count ? 'rejected' : 'left out'} by a surveyor`,
        action: count ? 'Restore' : 'Include',
        edit: 'restore',
      };
    case 'excluded':
      return {
        sign: '–',
        text: `${label}, left out by the rule: ${mark.reason ?? ''}`,
        action: count ? 'Count in' : 'Include',
        edit: 'restore',
      };
    case 'added':
      return { sign: `+${sign}`, text: 'added by a surveyor', action: 'Remove', edit: 'reject' };
    case 'counted': {
      const value = count
        ? ''
        : `, ${mark.value === null ? 'area unknown' : formatValue(mark.value, unit)}`;
      const counted = mark.reason ? `, counted in by a surveyor; the rule had: ${mark.reason}` : '';
      return {
        sign,
        text: `${label}${value}${counted}`,
        action: count ? 'Reject' : 'Leave out',
        edit: 'reject',
      };
    }
  }
}
