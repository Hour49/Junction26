import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawing, project } from '../api/fixtures';
import { mockApi, never, reply } from '../test/mockApi';
import {
  changeLines,
  extentOf,
  inPolygon,
  roomAt,
  roomsOf,
  signedArea,
  splitCites,
  stepsSummary,
  zoomFor,
} from './agent';
import { EditCard } from './EditCard';
import {
  answerTurn,
  conflictTurn,
  DID,
  dontKnowOptionsTurn,
  dontKnowTurn,
  editTurn,
  model,
  needsInputTurn,
  proposal,
  roomTurn,
} from './fixtures';
import { selectionOf } from './PlanPointer';
import { TurnCard } from './TurnCard';

const PID = project.id;
const DRAWING = `GET /api/drawings/${DID}`;
const DECIDE = `POST /api/projects/${PID}/chat/${editTurn.chat_id}/proposals/p1`;

afterEach(() => {
  cleanup();
});

function card(turn = answerTurn, onAsk = vi.fn()) {
  render(<TurnCard turn={turn} projectId={PID} busy={false} onAsk={onAsk} />);
  return onAsk;
}

describe('helpers', () => {
  it('AC-31 splitCites links only the [n] of listed sources', () => {
    expect(splitCites('A [1] and [2], not [3].', [1, 2])).toEqual([
      'A ',
      1,
      ' and ',
      2,
      ', not [3].',
    ]);
    expect(splitCites('no cites', [1])).toEqual(['no cites']);
  });
  it('AC-31 stepsSummary counts steps, time and cost', () => {
    expect(stepsSummary(answerTurn)).toBe('2 steps · 0.3 s · $0');
    expect(
      stepsSummary({ ...answerTurn, steps: answerTurn.steps.slice(0, 1), cost_usd: 0.012 }),
    ).toBe('1 step · 0.3 s · $0.01');
    expect(stepsSummary({ ...answerTurn, cost_usd: 0.004 })).toBe('2 steps · 0.3 s · <$0.01');
  });
  it('AC-32 changeLines: removed, new, rooms with before → after and the difference', () => {
    expect(changeLines(proposal)).toEqual([
      'Removed: Wall W4, 2.87 m, 0.12 m thick',
      'Bagno 1.01 + Stanza 1.02: 24.04 → 24.56 m² (+0.52 m²)',
    ]);
    expect(changeLines(roomTurn.edit as typeof proposal)).toEqual([
      'New: New wall, 2.10 m, 0.10 m thick',
      'Storage: new, 3.40 m²',
      'Stanza 1.02: 16.48 → 13.08 m² (−3.40 m²)',
    ]);
    expect(signedArea(0.001)).toBe('±0.00 m²');
  });
  it('AC-32 the plan zooms to the change: extent of every polygon, zoom 4 / 2 / 1', () => {
    expect(extentOf(proposal)).toEqual([0.3, 0.2, 0.52, 0.3]);
    expect(zoomFor([0.3, 0.2, 0.45, 0.3])).toBe(4);
    expect(zoomFor(extentOf(proposal))).toBe(2);
    expect(zoomFor([0, 0, 0.8, 0.1])).toBe(1);
  });
  it('AC-33 a click is a room, a drag is a region', () => {
    const plan = { drawing_id: DID, name: 'Drawn plan 1' };
    expect(selectionOf(plan, 1, [0.1, 0.1, 0.13, 0.145])).toEqual({
      sel: { kind: 'room', drawing_id: DID, page: 1, box: [0.1, 0.1, 0.13, 0.145] },
      chip: 'Room on Drawn plan 1, page 1',
    });
    expect(selectionOf(plan, 1, [0.1, 0.1, 0.3, 0.2]).sel.kind).toBe('region');
    expect(selectionOf(plan, 1, [0.1, 0.1, 0.3, 0.2]).chip).toBe('Area on Drawn plan 1, page 1');
  });
  it('AC-33 a click on a room of the model sends its id and names it; outside every room the point alone', () => {
    const plan = { drawing_id: DID, name: 'Drawn plan 1' };
    const rooms = roomsOf(model);
    expect(selectionOf(plan, 1, [0.185, 0.18, 0.215, 0.225], rooms)).toEqual({
      sel: { kind: 'room', drawing_id: DID, page: 1, ref: 'R3', box: [0.185, 0.18, 0.215, 0.225] },
      chip: 'Room Bagno 1.01',
    });
    // no polygon: its box; no label: its type
    expect(selectionOf(plan, 1, [0.385, 0.18, 0.415, 0.225], rooms).chip).toBe('Room bedroom');
    expect(selectionOf(plan, 1, [0.785, 0.78, 0.815, 0.825], rooms).chip).toBe(
      'Room on Drawn plan 1, page 1',
    );
    expect(selectionOf(plan, 2, [0.185, 0.18, 0.215, 0.225], rooms).sel.ref).toBeUndefined();
  });
  it('AC-33 inPolygon on a concave L, roomsOf without rooms', () => {
    const L: [number, number][] = [
      [0, 0],
      [2, 0],
      [2, 1],
      [1, 1],
      [1, 2],
      [0, 2],
    ];
    expect(inPolygon([0.5, 1.5], L)).toBe(true);
    expect(inPolygon([1.5, 1.5], L)).toBe(false);
    expect(roomsOf({ schema: 'extraction_v1' })).toEqual([]);
    expect(roomAt(roomsOf(model), 1, [0.2, 0.2])?.id).toBe('R3');
  });
});

describe('TurnCard', () => {
  it('AC-31 answer: [n] links to its source, sources with Show it, confidence, steps disclosure', () => {
    card();
    const cite = screen.getByRole('link', { name: /Source 1: Bagno 1.01/ });
    const show = screen.getByRole('link', { name: 'Show it' });
    expect(cite.getAttribute('href')).toBe(
      `#/p/${PID}/d/${DID}/engineer?page=1&box=0.31%2C0.22%2C0.38%2C0.29`,
    );
    expect(show.getAttribute('href')).toBe(cite.getAttribute('href'));
    const sources = within(screen.getByRole('list', { name: 'Sources' }));
    expect(sources.getByText('Bagno 1.01 · Drawn plan 1, page 1')).toBeTruthy();
    const conf = sources.getByText(/Confidence: High/);
    expect(conf.getAttribute('title')).toBe('Read from the drawn room outline and its label.');
    expect(screen.getByText('2 steps · 0.3 s · $0')).toBeTruthy();
    expect(screen.getByText('Asked the drawings: room area')).toBeTruthy();
  });

  it('AC-31 dont_know: the refusal look, "I don\'t know" headline and the reason; a failed step is marked', () => {
    const { container } = render(
      <TurnCard turn={dontKnowTurn} projectId={PID} busy={false} onAsk={vi.fn()} />,
    );
    expect(container.querySelector('.ag-card--dont_know')).toBeTruthy();
    expect(screen.getByText("I don't know.")).toBeTruthy();
    expect(screen.getByText(/does not say which walls carry load/)).toBeTruthy();
    expect(screen.getByText(/failed/).closest('li')?.textContent).toBe(
      'Searched the building code · failed',
    );
    expect(screen.queryByRole('list', { name: 'Sources' })).toBeNull();
  });

  it('AC-31 conflict: both values with both sources; a level of null shows no confidence', () => {
    card(conflictTurn);
    expect(screen.getByText('The sources disagree.')).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /^Source [12]/ })).toHaveLength(2);
    expect(screen.getAllByText(/Confidence:/)).toHaveLength(1);
  });

  it('AC-31 needs_input: options are chips that send option.message', () => {
    const onAsk = card(needsInputTurn);
    fireEvent.click(screen.getByRole('button', { name: 'Bagno 1.05' }));
    expect(onAsk).toHaveBeenCalledWith('Remove the wall between Bagno 1.05 and the bedroom');
  });

  it('AC-31 options on any kind: a dont_know offers questions to try that send option.message', () => {
    const onAsk = card(dontKnowOptionsTurn);
    expect(screen.getByText("I don't know.")).toBeTruthy();
    const group = screen.getByRole('group', { name: 'Try one of these instead' });
    expect(within(group).getAllByRole('button')).toHaveLength(2);
    fireEvent.click(within(group).getByRole('button', { name: 'How big is Bagno 1.01?' }));
    expect(onAsk).toHaveBeenCalledWith('How big is Bagno 1.01?');
    cleanup();
    card(dontKnowTurn); // options null: no chips, no label
    expect(screen.queryByRole('group', { name: 'Try one of these instead' })).toBeNull();
    expect(screen.queryByText('Try one of these instead')).toBeNull();
  });

  it('AC-32 edit turn renders the edit card', () => {
    mockApi({ [DRAWING]: never() });
    card(editTurn);
    expect(screen.getByRole('figure', { name: 'Proposed plan' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Accept' })).toBeTruthy();
  });
});

describe('EditCard', () => {
  function edit(onDecided = vi.fn(), decided: unknown = { ...proposal, state: 'accepted' }) {
    const api = mockApi({ [DRAWING]: drawing, [DECIDE]: decided });
    const r = render(
      <EditCard
        proposal={proposal}
        projectId={PID}
        chatId={editTurn.chat_id}
        onDecided={onDecided}
      />,
    );
    return { api, onDecided, ...r };
  }

  it('AC-32 overlay: demolished, changed room with its badge; legend in words; Before hides the overlay', async () => {
    const { container } = edit();
    await waitFor(() => {
      expect(container.querySelector('.ag-overlay')).toBeTruthy();
    });
    expect(container.querySelectorAll('.ag-overlay .ag-removed')).toHaveLength(1);
    expect(container.querySelector('.ag-overlay .ag-room')?.getAttribute('fill')).toMatch(
      /^url\(#ag-hatch-/,
    );
    expect(screen.getByText('Bagno 1.01 + Stanza 1.02 · 24.04 → 24.56 m²')).toBeTruthy();
    for (const w of [
      'Existing',
      'Demolished (yellow, dashed)',
      'New (red, solid)',
      'Changed room (hatched)',
    ])
      expect(screen.getByText(w)).toBeTruthy();
    const before = screen.getByRole('button', { name: 'Before' });
    const after = screen.getByRole('button', { name: 'After' });
    expect(after.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(before);
    expect(before.getAttribute('aria-pressed')).toBe('true');
    expect(container.querySelector('.ag-overlay')).toBeNull();
    expect(screen.getByRole('img', { name: 'Page 1, as drawn' })).toBeTruthy();
  });

  it('AC-32 change list, unknowns, flags and the note', () => {
    edit();
    expect(screen.getByText('Bagno 1.01 + Stanza 1.02: 24.04 → 24.56 m² (+0.52 m²)')).toBeTruthy();
    expect(screen.getByText(/Whether wall W4 is load-bearing/)).toBeTruthy();
    expect(screen.getByText(/waterproofing is redone/)).toBeTruthy();
    expect(
      screen.getByText(
        'Proposed from the drawn geometry. Structure, services and permits are not checked.',
      ),
    ).toBeTruthy();
  });

  it('AC-32 Accept posts the decision and the buttons give way to "Accepted"', async () => {
    const { api, onDecided } = edit();
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));
    expect(await screen.findByRole('status')).toHaveProperty('textContent', 'Accepted');
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({ action: 'accept' });
    expect(onDecided).toHaveBeenCalledWith(expect.objectContaining({ state: 'accepted' }));
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
  });

  it('AC-32 a 409 keeps the buttons and says why', async () => {
    edit(vi.fn(), reply(409, { detail: 'already decided', code: 'conflict' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(/already decided/);
    expect(screen.getByRole('button', { name: 'Reject' })).toBeTruthy();
  });
});
