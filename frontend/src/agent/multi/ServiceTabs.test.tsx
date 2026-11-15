import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, project } from '../../api/fixtures';
import { mockApi } from '../../test/mockApi';
import { EditCard } from '../EditCard';
import { DID, editTurn, proposal } from '../fixtures';
import { sheetFocus } from './ServiceTabs';
import { followed, heatingPicture, PIC, pictured, services, ventilation } from './fixtures';
import {
  focusOf,
  markStatus,
  onSheet,
  ordered,
  pictureOf,
  placeOfAction,
  strikeOf,
  tabNote,
} from './services';

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

  it('a lane is in focus on the changed walls, its terminals and what it proposes, plus a tenth', () => {
    // x: the duct seen end-on at 0.36 to the terminal at 0.47 (the run from 0.33 is a line: left out);
    // y: the wall, 0.20 to 0.30
    const box = focusOf(ventilation, followed);
    [0.349, 0.189, 0.481, 0.311].forEach((v, i) => {
      expect(box?.[i]).toBeCloseTo(v);
    });
    expect(services.disciplines[0] && focusOf(services.disciplines[0], followed)).toBeNull();
  });

  it("a services picture is in focus on the edit's own outlines, not on every symbol read on the sheet", () => {
    // R1 edits 10c: the plumbing picture's lane carries every symbol the reader found (562 on P-101), so the
    // box of them all was nearly the whole sheet and the struck-out wall sat cut off at its right edge
    const far = {
      ref: 'H9',
      global_id: '',
      kind: 'radiator',
      label: 'radiator',
      line: [],
      at: [0.9, 0.9] as [number, number],
    };
    const lane = {
      ...heatingPicture,
      marks: [...heatingPicture.marks, far],
      picture: {
        ...heatingPicture.picture,
        marks: [
          ...heatingPicture.picture.marks,
          { ref: 'H9', line: [], at: [0.95, 0.92] as [number, number] },
        ],
      },
    };
    const box = sheetFocus(lane, lane.picture);
    expect(box).not.toBeNull();
    const [x0, y0, x1, y1] = box ?? [0, 0, 0, 0];
    expect(x0 <= 0.45 && y0 <= 0.3 && x1 >= 0.46 && y1 >= 0.4).toBe(true); // the removed strip is in view
    expect(x1).toBeLessThan(0.7); // the far symbol is not
    expect(y1).toBeLessThan(0.7);
  });

  it('an action is placed at the middle of what it draws; a tally has no place', () => {
    const [through, reseat, , , tally] = ventilation.actions;
    expect(reseat && placeOfAction(ventilation, reseat)).toEqual([0.398, 0.226]);
    expect(through && placeOfAction(ventilation, through)).toEqual([0.4075, 0.27]);
    expect(tally && placeOfAction(ventilation, tally)).toBeNull();
  });
});

describe('discipline tabs on the edit card', () => {
  it('a discipline tab zooms the plan to what it draws; Plan and a lane that draws nothing keep the edit', async () => {
    const { container } = await card();
    const width = () => container.querySelector<HTMLElement>('.vw-frame')?.style.width;
    expect(width()).toBe('200%'); // the merged room is 0.22 of the page wide
    fireEvent.click(tab(/Ventilation/));
    expect(width()).toBe('400%'); // the wall and its terminals span 0.13
    fireEvent.click(tab(/Plumbing/));
    expect(width()).toBe('200%');
    fireEvent.click(tab('Plan'));
    expect(width()).toBe('200%');
  });

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

describe('a discipline picture with the edit drawn on it (AC-40..44)', () => {
  const sheet = {
    ...drawing,
    id: PIC,
    file: 'heating/EG-heating.png',
    pages: drawing.pages.map((pg) => ({ ...pg, url: `/api/drawings/${PIC}/pages/1.png` })),
  };
  const pictureCard = async () => {
    const api = mockApi({
      [`GET /api/drawings/${DID}`]: drawing,
      [`GET /api/drawings/${PIC}`]: sheet,
    });
    const r = render(
      <EditCard proposal={pictured} projectId={project.id} chatId={editTurn.chat_id} />,
    );
    await waitFor(() => {
      expect(r.container.querySelector('.ag-overlay')).toBeTruthy();
    });
    return { ...r, api };
  };
  const pageImage = (c: HTMLElement) => c.querySelector<HTMLImageElement>('.ag-planbox img');

  it('the lane on its sheet: marks at their sheet places, nothing moved or newly run', () => {
    const lane = onSheet(heatingPicture, heatingPicture.picture);
    expect(lane.marks.find((m) => m.ref === 'H1')?.at).toEqual([0.448, 0.34]);
    expect(lane.marks.find((m) => m.ref === 'H2')?.line).toEqual([
      [0.41, 0.37],
      [0.5, 0.37],
    ]);
    expect(lane.actions.every((a) => a.moved_to === null && a.paths.length === 0)).toBe(true);
    expect(pictureOf(ventilation)).toBeNull();
  });

  it('a removed strip is struck along its long side', () => {
    const strip = heatingPicture.picture.removed[0] ?? [];
    expect(strikeOf(strip)).toEqual([
      [0.455, 0.3],
      [0.455, 0.4],
    ]);
  });

  it('AC-40/42 the tab shows its own sheet, the edit struck out there, the marks there, and why it was paired', async () => {
    const { container } = await pictureCard();
    expect(pageImage(container)?.getAttribute('src')).toContain(DID); // Plan first
    fireEvent.click(tab(/Heating/));
    await waitFor(() => {
      expect(pageImage(container)?.getAttribute('src')).toContain(PIC);
    });
    expect(pageImage(container)?.getAttribute('alt')).toBe(
      'heating/EG-heating.png, page 1, with the proposed change drawn on it',
    );
    expect(container.querySelector('.ag-strike')).toBeTruthy();
    expect(container.querySelectorAll('.ag-planbox .ag-removed')).toHaveLength(1);
    const radiator = container.querySelector<HTMLElement>('.ms-dot[title="radiator"]');
    expect(parseFloat(radiator?.style.left ?? '')).toBeCloseTo(44.8);
    expect(parseFloat(radiator?.style.top ?? '')).toBeCloseTo(34);
    expect(radiator?.textContent).toBe('!');
    expect(
      screen.getByText("Paired by the sheets' names: same floor in the title block: 'EG' on both"),
    ).toBeTruthy();
  });

  it('AC-41 Before: the sheet as drawn, its marks without status, no edit', async () => {
    const { container } = await pictureCard();
    fireEvent.click(tab(/Heating/));
    await waitFor(() => {
      expect(pageImage(container)?.getAttribute('src')).toContain(PIC);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Before' }));
    expect(pageImage(container)?.getAttribute('alt')).toBe(
      'heating/EG-heating.png, page 1, as drawn',
    );
    expect(container.querySelector('.ag-strike')).toBeNull();
    expect(container.querySelector('.ag-planbox .ag-removed')).toBeNull();
    expect(container.querySelector<HTMLElement>('.ms-dot[title="radiator"]')?.textContent).toBe('');
  });

  it('AC-43 Not this sheet: back to the plan, the lane not checked, and undone with Use this sheet again', async () => {
    const { container } = await pictureCard();
    fireEvent.click(tab(/Heating/));
    await waitFor(() => {
      expect(pageImage(container)?.getAttribute('src')).toContain(PIC);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Not this sheet' }));
    await waitFor(() => {
      expect(pageImage(container)?.getAttribute('src')).toContain(DID);
    });
    expect(
      screen.getByText("Not checked: you said this is not this floor's heating sheet."),
    ).toBeTruthy();
    expect(tab(/Heating/).textContent).toBe('Heatingnot checked');
    expect(screen.queryByText(/The radiator on the removed wall/)).toBeNull();
    expect(container.querySelector('.ms-dot')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Use this sheet again' }));
    await waitFor(() => {
      expect(pageImage(container)?.getAttribute('src')).toContain(PIC);
    });
  });

  it('AC-45 All sheets: the plan and each picture side by side, the edit on each; Before clears every one', async () => {
    const { container } = await pictureCard();
    fireEvent.click(tab('All sheets'));
    const panels = () => [...container.querySelectorAll<HTMLElement>('.ms-sync-panel')];
    await waitFor(() => {
      expect(panels().map((p) => p.querySelector('img')?.getAttribute('src') ?? '')).toEqual([
        expect.stringContaining(DID),
        expect.stringContaining(PIC),
      ]);
    });
    expect(panels().map((p) => p.getAttribute('aria-label'))).toEqual([
      'Plan, with the proposed change',
      'Heating: heating/EG-heating.png, with the proposed change',
    ]);
    const [plan, heating] = panels();
    expect(plan?.querySelectorAll('.ag-removed')).toHaveLength(1); // the plan's own overlay
    expect(heating?.querySelector('.ag-strike')).toBeTruthy(); // the edit on the heating sheet
    expect(heating?.querySelector<HTMLElement>('.ms-dot[title="radiator"]')?.textContent).toBe('!');
    fireEvent.click(screen.getByRole('button', { name: 'Before' }));
    expect(container.querySelector('.ms-sync .ag-removed')).toBeNull();
    expect(container.querySelector('.ms-sync .ag-strike')).toBeNull();
    // a panel opens its own tab
    fireEvent.click(within(heating as HTMLElement).getByRole('button', { name: 'Open Heating' }));
    await waitFor(() => {
      expect(container.querySelectorAll('.ms-sync-panel')).toHaveLength(0);
    });
    expect(tab(/^Heating/).getAttribute('aria-pressed')).toBe('true');
  });

  it('AC-45 no All sheets without a picture, nor once its only picture is refused', async () => {
    await card();
    expect(
      within(screen.getByRole('group', { name: 'Discipline' })).queryByRole('button', {
        name: 'All sheets',
      }),
    ).toBeNull();
    cleanup();
    await pictureCard();
    fireEvent.click(tab(/Heating/));
    fireEvent.click(await screen.findByRole('button', { name: 'Not this sheet' }));
    expect(
      within(screen.getByRole('group', { name: 'Discipline' })).queryByRole('button', {
        name: 'All sheets',
      }),
    ).toBeNull();
  });

  it('AC-44 a lane without a picture is drawn over the plan as before', async () => {
    const { container } = await pictureCard();
    fireEvent.click(tab(/Ventilation/));
    expect(pageImage(container)?.getAttribute('src')).toContain(DID);
    expect(container.querySelector('.ag-strike')).toBeNull();
    expect(screen.queryByText(/Paired by/)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Not this sheet' })).toBeNull();
  });
});
