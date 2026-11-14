// resolver.md RS-15: a row whose model pick is in use says so in its state cell.
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
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
