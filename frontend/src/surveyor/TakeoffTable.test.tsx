// resolver.md RS-15: a row whose model pick is in use says so in its state cell.
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Row, Takeoff } from '../api';
import { projectReviewResolved, takeoff } from '../api/fixtures';
import { TakeoffTable } from './TakeoffTable';

afterEach(cleanup);

it('RS-15 the takeoff row with a pick in use reads Picked by Carbon in its state cell', () => {
  const pick = projectReviewResolved.conflicts[0]?.resolved;
  const rows = takeoff.quantities.map((q, i): Row =>
    i === 0 ? { ...q, needs_person: false, resolved: pick } : { ...q, resolved: null },
  );
  const t: Takeoff = { ...takeoff, quantities: rows, review_queue: [] };
  render(<TakeoffTable takeoff={t} selected={null} onSelect={() => undefined} />);
  const cell = screen.getByText('Picked by Carbon');
  expect(cell.closest('tr')?.getAttribute('data-key')).toBe(rows[0]?.key);
  expect(cell.getAttribute('title')).toBe('gemini-4-carbon');
  expect(screen.getAllByText('Picked by Carbon')).toHaveLength(1);
});

// R3-G9: on a phone (<= 640 px) the rows are cards and the ones that need the surveyor come first: a row waiting
// on a person, then a row with a conflict; the takeoff order otherwise. Desktop keeps the takeoff order.
describe('R3-G9 phone order', () => {
  const keys = () =>
    [...document.querySelectorAll('tr[data-key]')].map((r) => r.getAttribute('data-key'));
  const rows = takeoff.quantities.slice(0, 3).map((q, i): Row => ({
    ...q,
    key: `k${String(i)}`,
    needs_person: i === 2,
    conflict: i === 1 ? (takeoff.quantities.find((r) => r.conflict)?.conflict ?? null) : null,
    resolved: null,
  }));
  const t: Takeoff = { ...takeoff, quantities: rows, review_queue: [] };
  const phone = (on: boolean) => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: on && q === '(max-width: 640px)',
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  };
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('on a phone: needs-you first, then the conflict, then the rest', () => {
    phone(true);
    render(<TakeoffTable takeoff={t} selected={null} onSelect={() => undefined} />);
    expect(keys()).toEqual(['k2', 'k1', 'k0']);
  });

  it('on a desktop: the takeoff order', () => {
    phone(false);
    render(<TakeoffTable takeoff={t} selected={null} onSelect={() => undefined} />);
    expect(keys()).toEqual(['k0', 'k1', 'k2']);
  });
});
