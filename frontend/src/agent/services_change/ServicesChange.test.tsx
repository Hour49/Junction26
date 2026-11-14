import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { project } from '../../api/fixtures';
import { mockApi } from '../../test/mockApi';
import { EditCard } from '../EditCard';
import { editTurn } from '../fixtures';
import { checkLine, factLine, shownRuns } from './change';
import { moved, PICTURE, servicesProposal } from './fixtures';

afterEach(cleanup);

const card = (p = servicesProposal) => {
  const { calls } = mockApi({}); // any request fails the test
  return {
    calls,
    ...render(<EditCard proposal={p} projectId={project.id} chatId={editTurn.chat_id} />),
  };
};
const ids = (c: HTMLElement, sel: string) =>
  [...c.querySelectorAll(sel)].map((el) => el.getAttribute('data-id'));

describe('services change helpers (SV-30)', () => {
  it('a fact reads before → after with its system, size and unit', () => {
    expect(moved.facts.map(factLine)).toEqual([
      'pipe length, Heating 1, DN15: 38.50 → 43.00 m',
      'pipe fitting count: 12 → 13',
    ]);
  });

  it('a check says passed or failed in words, not by its mark alone', () => {
    expect(moved.checks.map(checkLine)).toEqual([
      { mark: '✓', text: 'Passed: The heating network is still in one piece.' },
      { mark: '✕', text: 'Failed: The new run passes a door.' },
    ]);
  });

  it('a halved main is neither removed nor added; the rerouted branch is both', () => {
    const runs = shownRuns(moved);
    expect(runs.removed.map((r) => r.id)).toEqual(['E31']);
    expect(runs.added.map((r) => r.id)).toEqual(['N1']);
  });
});

describe('the edit card with a services change (SV-30)', () => {
  it('shows the storey picture, not the drawing page', () => {
    const { calls } = card();
    const img = screen.getByRole('img', { name: /storey L2, with the proposed change/ });
    expect(img.getAttribute('src')).toBe(PICTURE);
    expect(calls.some((c) => c.url.includes('/api/drawings/'))).toBe(false);
  });

  it('draws removed runs dashed, added runs thick and the moved terminal as a hollow mark with an arrow', () => {
    const { container } = card();
    expect(ids(container, '.sc-overlay .sc-removed')).toEqual(['E31']);
    expect(ids(container, '.sc-overlay .sc-added')).toEqual(['N1']);
    expect(container.querySelectorAll('[data-id="E31"] line')).toHaveLength(1);
    expect(container.querySelectorAll('[data-id="N1"] line')).toHaveLength(2);
    const from = container.querySelector('.sc-from');
    expect([from?.getAttribute('cx'), from?.getAttribute('cy')]).toEqual(['41%', '32%']);
    const arrow = container.querySelector('.sc-arrow');
    expect([arrow?.getAttribute('x2'), arrow?.getAttribute('y2')]).toEqual(['47%', '38%']);
  });

  it('lists the change, the facts and the checks in words, then the unknowns and flags', () => {
    card();
    const list = screen.getByRole('list', { name: 'Services change' });
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Moved: Radiator 22-600', 'Removed: Pipe DN15, 2.00 m', 'New: Pipe DN15, 6.50 m']);
    const facts = screen.getByRole('list', { name: 'Before → after' });
    expect(within(facts).getAllByRole('listitem')[0]?.textContent).toBe(
      'pipe length, Heating 1, DN15: 38.50 → 43.00 m',
    );
    const checks = screen.getByRole('list', { name: 'Checks' });
    expect(
      within(checks)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      '✓Passed: The heating network is still in one piece.',
      '✕Failed: The new run passes a door.',
    ]);
    expect(screen.getByText(moved.unknowns[0] ?? '')).toBeTruthy();
    expect(screen.getByText(moved.flags[0]?.text ?? '')).toBeTruthy();
  });

  it('Before hides the overlay; the toggle is two keyboard-reachable buttons', () => {
    const { container } = card();
    const group = screen.getByRole('group', { name: 'Show the storey' });
    const before = within(group).getByRole('button', { name: 'Before' });
    fireEvent.click(before);
    expect(before.getAttribute('aria-pressed')).toBe('true');
    expect(container.querySelector('.sc-overlay')).toBeNull();
    expect(screen.getByRole('img', { name: /storey L2, as it is/ })).toBeTruthy();
    fireEvent.click(within(group).getByRole('button', { name: 'After' }));
    expect(container.querySelector('.sc-overlay')).toBeTruthy();
  });

  it('says so when there is no picture', () => {
    card({ ...servicesProposal, services_change: { ...moved, picture: null } });
    expect(screen.getByText('The storey picture is not available for this change.')).toBeTruthy();
    expect(screen.queryByRole('img')).toBeNull();
  });
});
