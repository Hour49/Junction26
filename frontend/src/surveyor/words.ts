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

export function statusText(row: Pick<Row, 'status' | 'needs_person'>): string {
  return row.needs_person ? `${STATUS[row.status]} · needs you` : STATUS[row.status];
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
