// The edit card's building rules (docs/specs/plan-edit-law-check.md §3, LC-12 to LC-15).
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, info, project } from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { mockApi } from '../test/mockApi';
import type { ChatTurn } from './agent';
import { DID, lawRoomTurn, noPackRoomTurn } from './fixtures';
import { TurnCard } from './TurnCard';

const PID = project.id;

const scrolled = vi.fn();
beforeAll(() => {
  Element.prototype.scrollIntoView = scrolled;
});
afterEach(() => {
  cleanup();
});

/** The turn's card, with /api/info answered (the country names) unless `withInfo` is false. */
async function card(turn: ChatTurn, withInfo = true) {
  mockApi({ [`GET /api/drawings/${DID}`]: drawing, 'GET /api/info': info });
  const body = (
    <TurnCard
      turn={turn}
      projectId={PID}
      project={project}
      pack={null}
      busy={false}
      onAsk={vi.fn()}
    />
  );
  render(withInfo ? <InfoProvider>{body}</InfoProvider> : body);
  if (withInfo) await screen.findByRole('region', { name: 'Building rules · Canton of Zürich' });
}

const rows = () =>
  within(screen.getByRole('list', { name: 'Rule checks' })).getAllByRole('listitem');

it('LC-12 heading with the country, rows newly_fails first, each status as icon and word', async () => {
  await card(lawRoomTurn);
  expect(screen.getByRole('heading', { name: 'Building rules · Canton of Zürich' })).toBeTruthy();
  const heads = rows().map((r) => r.querySelector('.ag-law-head')?.textContent);
  expect(heads).toEqual([
    '✕ Would not meet A bedroom or living room is at least 10 m2 (canton of Zürich)',
    "✕ Still doesn't meet An entrance door is at least 0.8 m wide",
    "! Can't tell A habitable room is at least 2.4 m high",
    '✓ Meets now A habitable room has a window (canton of Zürich)',
  ]);
});

it('LC-12 a row: subject before → after against the limit, the clause link in a new tab, the quote open for a new fail', async () => {
  await card(lawRoomTurn);
  const [fail, , unclear] = rows() as [HTMLElement, HTMLElement, HTMLElement];
  expect(fail.querySelector('.ag-law-values')?.textContent).toBe(
    'Stanza 1.02: 16.48 m² → 8.9 m² · at least 10 m²',
  );
  const link = within(fail).getByRole('link', { name: /§ 303 Abs. 1/ });
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toContain('noopener');
  const quote = fail.querySelector('details');
  expect(quote?.open).toBe(true);
  expect(within(fail).getByText('Translation ours, unofficial')).toBeTruthy();
  expect(within(fail).getByText(/mindestens 10 m²/)).toBeTruthy();
  expect(unclear.querySelector('.ag-law-values')?.textContent).toBe(
    'Storage: not known → not known · at least 2.4 m',
  );
  expect(within(unclear).getByText('rooms of a kind we could not tell')).toBeTruthy();
  expect(unclear.querySelector('details')).toBeNull(); // no quote, no disclosure
  expect(screen.getByText('6 other checks unchanged')).toBeTruthy();
  const section = screen.getByRole('region', { name: 'Building rules · Canton of Zürich' });
  expect(section.lastElementChild?.textContent).toMatch(/^A pre-check of 2 rules/);
});

it('LC-13 the AI block with its label, then at most 3 other rules not already shown', async () => {
  await card(lawRoomTurn);
  expect(
    screen.getByText(
      "AI reading of the law, checked against the clause's number; not a rule check",
    ),
  ).toBeTruthy();
  const ai = within(screen.getByRole('list', { name: 'The AI also found in the law' })).getByRole(
    'listitem',
  );
  expect(ai.querySelector('.ag-law-head')?.textContent).toBe('✕ Would not meet § 305 Abs. 1 · PBG');
  expect(ai.querySelector('.ag-law-values')?.textContent).toBe('Storage: 3.4 m² · at least 4 m²');
  expect(ai.querySelector('details')?.open).toBe(false);
  const other = within(screen.getByRole('list', { name: 'Other rules to read' })).getAllByRole(
    'link',
  );
  expect(other.map((a) => a.textContent)).toEqual([
    '§ 302 Abs. 2 · Planning and Building Act',
    '§ 306 Abs. 1 · Planning and Building Act',
    '§ 307 Abs. 1 · Planning and Building Act',
  ]);
});

it('LC-13 without /api/info the heading names the pack', async () => {
  await card(lawRoomTurn, false);
  expect(
    screen.getByRole('heading', { name: 'Building rules · Canton of Zürich building act' }),
  ).toBeTruthy();
});

it('LC-14 no pack: the pick-a-country line and a button that opens the header picker', async () => {
  const picker = document.createElement('button');
  picker.className = 'country-button';
  const opened = vi.fn();
  picker.addEventListener('click', opened);
  document.body.append(picker);
  await card(noPackRoomTurn, false);
  expect(
    screen.getByText('Pick a country to check this change against its building rules'),
  ).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Pick a country' })).toBeNull(); // info not loaded: no packs
  cleanup();
  mockApi({ [`GET /api/drawings/${DID}`]: drawing, 'GET /api/info': info });
  render(
    <InfoProvider>
      <TurnCard
        turn={noPackRoomTurn}
        projectId={PID}
        project={project}
        pack={null}
        busy={false}
        onAsk={vi.fn()}
      />
    </InfoProvider>,
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Pick a country' }));
  expect(opened).toHaveBeenCalledOnce();
  expect(screen.queryByRole('list', { name: 'Rule checks' })).toBeNull();
  picker.remove();
});

it('LC-15 a subject highlights its ev mark, else the proposal room that names it', async () => {
  await card(lawRoomTurn);
  await waitFor(() => {
    expect(document.querySelector('.ag-overlay')).toBeTruthy();
  });
  fireEvent.click(screen.getAllByRole('button', { name: 'Stanza 1.02' })[0] as HTMLElement);
  expect(document.querySelector('.ag-hot')?.getAttribute('points')).toBe(
    '0.55,0.3 0.7,0.3 0.7,0.4 0.55,0.4',
  );
  expect(scrolled).toHaveBeenCalled(); // the plan comes into view
  // "Storage" has no ev: the new room of the proposal
  fireEvent.click(screen.getAllByRole('button', { name: 'Storage' })[0] as HTMLElement);
  expect(document.querySelector('.ag-hot')?.getAttribute('points')).toBe(
    '0.6,0.4 0.7,0.4 0.7,0.48 0.6,0.48',
  );
});
