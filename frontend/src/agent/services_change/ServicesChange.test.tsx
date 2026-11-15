import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { project } from '../../api/fixtures';
import { mockApi } from '../../test/mockApi';
import { EditCard } from '../EditCard';
import { editTurn } from '../fixtures';
import { checkLine, factLine, shownRuns, zoomBox, type ServicesChange } from './change';
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

  it('the close-up is a square of the page around everything that changed, inside the page', () => {
    const box = zoomBox(moved, shownRuns(moved));
    expect(box.s).toBeCloseTo(0.2); // a 0.07 change, 0.05 margin a side, at least a fifth of the page
    expect([box.x, box.y].map((v) => Math.round(v * 1000))).toEqual([335, 245]);
    const one = { id: 'E12', label: 'Radiator' };
    const edge: ServicesChange = {
      ...moved,
      moved: [{ ...one, from: [0.97, 0.98], to: [0.99, 0.99] }],
    };
    const corner = zoomBox(edge, { removed: [], added: [] });
    expect([corner.x + corner.s, corner.y + corner.s].map((v) => Math.round(v * 1000))).toEqual([
      1000, 1000,
    ]);
    const wide: ServicesChange = { ...moved, moved: [{ ...one, from: [0, 0], to: [1, 1] }] };
    expect(zoomBox(wide, { removed: [], added: [] })).toEqual({ x: 0, y: 0, s: 1 });
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

  it('opens close up on the change, the whole floor one tap away (#566)', () => {
    const { container } = card();
    const view = screen.getByRole('group', { name: 'Picture' });
    const close = within(view).getByRole('button', { name: 'Close-up' });
    expect(close.getAttribute('aria-pressed')).toBe('true');
    const img = screen.getByRole('img', { name: /storey L2, with the proposed change, close up/ });
    expect(img.style.transform).toBe('scale(5) translate(-33.5%, -24.5%)');
    const from = container.querySelector('.sc-from'); // (0.41 - 0.335) / 0.2 of the close-up
    expect([from?.getAttribute('cx'), from?.getAttribute('cy')]).toEqual(['37.5%', '37.5%']);
    fireEvent.click(within(view).getByRole('button', { name: 'Whole floor' }));
    expect(img.style.transform).toBe('');
    expect(container.querySelector('.sc-from')?.getAttribute('cx')).toBe('41%');
  });

  it('marks the new runs to draw on and the new place to slide from the old one (#566)', () => {
    const { container } = card();
    const added = container.querySelectorAll('.sc-overlay .sc-added line');
    expect([...added].every((l) => l.getAttribute('pathLength') === '1')).toBe(true);
    // a removed run keeps its own length: pathLength would stretch its dashes into a solid line
    expect(
      container.querySelector('.sc-overlay .sc-removed line')?.hasAttribute('pathLength'),
    ).toBe(false);
    const to = container.querySelector<SVGElement>('.sc-to');
    expect([to?.style.getPropertyValue('--dx'), to?.style.getPropertyValue('--dy')]).toEqual([
      '-30%',
      '-30%',
    ]);
    expect(container.querySelector('.sc-ring')).toBeTruthy(); // a ring, not colour alone
    expect(screen.getByText(/New place \(filled mark with a ring\)/)).toBeTruthy();
  });

  it('draws removed runs dashed, added runs thick and the moved terminal as a hollow mark with an arrow', () => {
    const { container } = card();
    fireEvent.click(screen.getByRole('button', { name: 'Whole floor' }));
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

  it('a services change says what was not checked for services, with no empty Changes list (QA)', () => {
    card();
    expect(
      screen.getByText(
        'Proposed from the services model in the IFC file. Structure, flow, pressure and permits are not checked.',
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/Structure, services and permits are not checked/)).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Changes' })).toBeNull();
  });

  it('says so when there is no picture', () => {
    card({ ...servicesProposal, services_change: { ...moved, picture: null } });
    expect(screen.getByText('The storey picture is not available for this change.')).toBeTruthy();
    expect(screen.queryByRole('img')).toBeNull();
  });
});
