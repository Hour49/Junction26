import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, project } from '../../api/fixtures';
import { mockApi } from '../../test/mockApi';
import { EditCard } from '../EditCard';
import { DID, editTurn, proposal } from '../fixtures';
import { followed, services, ventilation } from './fixtures';
import { markStatus, ordered, placeOfAction, tabNote } from './services';

afterEach(cleanup);

const card = async (p = followed) => {
  mockApi({ [`GET /api/drawings/${DID}`]: drawing });
  const r = render(<EditCard proposal={p} projectId={project.id} chatId={editTurn.chat_id} />);
  await waitFor(() => {
    expect(r.container.querySelector('.ag-overlay')).toBeTruthy();
  });
  return r;
};
const tab = (name: RegExp | string) =>
  within(screen.getByRole('group', { name: 'Discipline' })).getByRole('button', { name });
const classes = (c: HTMLElement, sel: string) =>
  [...c.querySelectorAll(sel)].map((el) => el.getAttribute('class'));

describe('services helpers', () => {
  it('a mark two actions name takes the stronger status', () => {
    expect(markStatus(ventilation).get('V3')).toBe('needs_decision'); // a1 stays, a3 needs_decision
    expect(markStatus(ventilation).get('V2')).toBe('stays');
    expect(markStatus(ventilation).has('V4')).toBe(false);
  });

  it('the list runs strongest first and keeps the server order within a status', () => {
    expect(ordered(ventilation.actions).map((a) => a.id)).toEqual(['a4', 'a3', 'a2', 'a1', 'a5']);
  });

  it('the tab note counts what changes or asks, and says why a lane was not checked', () => {
    expect(services.disciplines.map(tabNote)).toEqual([null, '3', 'not aligned', 'no model']);
  });

  it('an action is placed at the middle of what it draws; a tally has no place', () => {
    const [through, reseat, , , tally] = ventilation.actions;
    expect(reseat && placeOfAction(ventilation, reseat)).toEqual([0.398, 0.226]);
    expect(through && placeOfAction(ventilation, through)).toEqual([0.4075, 0.27]);
    expect(tally && placeOfAction(ventilation, tally)).toBeNull();
  });
});

describe('discipline tabs on the edit card', () => {
  it('a proposal without a follow-up has no tabs', async () => {
    await card(proposal);
    expect(screen.queryByRole('group', { name: 'Discipline' })).toBeNull();
  });

  it('Plan first, then one tab per discipline with its count or why it was not checked', async () => {
    const { container } = await card();
    const names = within(screen.getByRole('group', { name: 'Discipline' }))
      .getAllByRole('button')
      .map((b) => b.textContent);
    expect(names).toEqual([
      'Plan',
      'Plumbing',
      'Ventilation3',
      'Heatingnot aligned',
      'Electricalno model',
    ]);
    expect(tab('Plan').getAttribute('aria-pressed')).toBe('true');
    expect(container.querySelector('.ms-layer')).toBeNull();
    expect(screen.queryByRole('region', { name: /after the change/ })).toBeNull();
  });

  it('After draws each mark in its action status, the new place and the proposed connection', async () => {
    const { container } = await card();
    fireEvent.click(tab(/Ventilation/));
    expect(tab(/Ventilation/).getAttribute('aria-pressed')).toBe('true');
    expect(classes(container, '.ms-layer .ms-run')).toEqual(['ms-run ms--stays', 'ms-run']);
    expect(container.querySelectorAll('.ms-layer .ms-path')).toHaveLength(1);
    const dot = (label: string) =>
      container.querySelector(`.vw-frame .ms-dot[title="${label}"]`)?.getAttribute('class');
    expect(dot('air terminal, ø250, Supply')).toBe(
      'ms-dot ms-dot--terminal ms--follows ms-dot--old',
    );
    expect(dot('fire damper, Extract')).toBe('ms-dot ms-dot--terminal ms--needs_decision');
    expect(dot('air terminal, ø125, Supply')).toBe('ms-dot ms-dot--terminal ms--cut_off');
    expect(dot('duct, ø125, Supply')).toBe('ms-dot'); // a run seen end-on, no action
    const place = container.querySelector<HTMLElement>('.vw-frame .ms-dot--new');
    expect(parseFloat(place?.style.left ?? '')).toBeCloseTo(39.8);
    expect(parseFloat(place?.style.top ?? '')).toBeCloseTo(20.2);
    // The edit itself stays drawn under the services.
    expect(container.querySelectorAll('.ag-overlay .ag-removed')).toHaveLength(1);
  });

  it('Before draws the services as they are: no status, no new place, no proposed connection', async () => {
    const { container } = await card();
    fireEvent.click(tab(/Ventilation/));
    fireEvent.click(screen.getByRole('button', { name: 'Before' }));
    expect(classes(container, '.ms-layer .ms-run')).toEqual(['ms-run', 'ms-run']);
    expect(container.querySelector('.ms-path')).toBeNull();
    expect(container.querySelector('.vw-frame .ms-dot--new')).toBeNull();
    expect(container.querySelector('.vw-frame .ms-dot--old')).toBeNull();
    expect(classes(container, '.vw-frame .ms-dot').every((c) => !c?.includes('ms--'))).toBe(true);
    expect(container.querySelector('.ag-overlay .ag-removed')).toBeNull();
  });

  it('the panel says the lane in one line and lists the actions by status word, strongest first', async () => {
    await card();
    fireEvent.click(tab(/Ventilation/));
    const panel = screen.getByRole('region', { name: 'Ventilation after the change' });
    expect(within(panel).getByText(ventilation.line)).toBeTruthy();
    expect(
      within(panel).getByText(/625 elements of ventilation\.ifc on storey Ground floor/),
    ).toBeTruthy();
    const rows = within(panel).getAllByRole('listitem');
    expect(rows.slice(0, 5).map((r) => r.querySelector('.ms-status')?.textContent)).toEqual([
      '✕ Cut off · Supply',
      '! Needs a decision',
      '→ Follows',
      '= Stays · Extract',
      '= Stays',
    ]);
    expect(within(panel).getByText(/not checked against each other in 3D/)).toBeTruthy();
    expect(
      within(panel).getByText('Services model: Example University (MIT License)'),
    ).toBeTruthy();
    // A tally draws nothing, so it offers nothing to show.
    expect(within(panel).getAllByRole('button', { name: 'Show on the plan' })).toHaveLength(4);
  });

  it('Show on the plan marks the action on the plan; a second press takes it off', async () => {
    const { container } = await card();
    fireEvent.click(tab(/Ventilation/));
    const panel = screen.getByRole('region', { name: 'Ventilation after the change' });
    const show = within(panel).getAllByRole('button', { name: 'Show on the plan' })[3]; // a1, through
    if (!show) throw new Error('no button');
    fireEvent.click(show);
    expect(show.getAttribute('aria-pressed')).toBe('true');
    expect(classes(container, '.ms-layer .ms-run')[0]).toBe('ms-run ms--stays ms--picked');
    expect(container.querySelectorAll('.ms-layer .ms-halo')).toHaveLength(1);
    expect(container.querySelectorAll('.vw-frame .ms-dot.ms--picked')).toHaveLength(1); // the damper
    fireEvent.click(show);
    expect(container.querySelector('.ms--picked')).toBeNull();
    // Another tab drops the pick.
    fireEvent.click(show);
    fireEvent.click(tab('Plan'));
    fireEvent.click(tab(/Ventilation/));
    expect(container.querySelector('.ms--picked')).toBeNull();
  });

  it('a lane that was not checked says why and draws nothing', async () => {
    const { container } = await card();
    fireEvent.click(tab(/Electrical/));
    const panel = screen.getByRole('region', { name: 'Electrical after the change' });
    expect(panel.textContent).toBe(
      'Electrical: not checked, this project has no electrical model.Services model: Example University (MIT License)',
    );
    expect(container.querySelectorAll('.ms-layer *')).toHaveLength(0);
  });

  it('Accept and Reject stay on the card under a discipline tab', async () => {
    await card();
    fireEvent.click(tab(/Plumbing/));
    expect(screen.getByRole('button', { name: 'Accept' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeTruthy();
  });
});
