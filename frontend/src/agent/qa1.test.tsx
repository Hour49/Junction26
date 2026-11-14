// QA round 1 on agent/law-check (.agents/qa-law): the agent chat's frontend fixes, each test named by its QA id.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, info, project } from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { mockApi, reply } from '../test/mockApi';
import { blocksOf, inlineOf, roomName, type ChatTurn, type LawCheck } from './agent';
import { AgentChat } from './AgentChat';
import { EditCard } from './EditCard';
import { answerTurn, DID, editTurn, lawRoomTurn, lawZh, model, proposal } from './fixtures';
import { TurnCard } from './TurnCard';

const PID = project.id;
const scrolled = vi.fn();
beforeAll(() => {
  Element.prototype.scrollIntoView = scrolled;
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  scrolled.mockClear();
});

const card = (turn: ChatTurn) =>
  render(
    <TurnCard
      turn={turn}
      projectId={PID}
      project={project}
      pack={null}
      busy={false}
      onAsk={vi.fn()}
    />,
  );

// answers-1 = lawai-3 = edits-8, AC-31
const LAW_TEXT = `It depends:

- **Finland (631/2024):** at least **7 m²** [1]. ([Finlex](https://www.finlex.fi/fi/2024/631))
- **Zürich:** \`10 m²\`
> quoted
2. **In Stanza 1.08 (\`p2\`)**: <img src=x onerror=alert(1)> [bad](javascript:alert(1))`;

it('answers-1 blocksOf: paragraphs and lists, an ordered list keeps its first number, ">" dropped', () => {
  expect(blocksOf(LAW_TEXT)).toEqual([
    { kind: 'p', lines: ['It depends:'] },
    {
      kind: 'ul',
      lines: [
        '**Finland (631/2024):** at least **7 m²** [1]. ([Finlex](https://www.finlex.fi/fi/2024/631))',
        '**Zürich:** `10 m²`',
      ],
    },
    { kind: 'p', lines: ['quoted'] },
    {
      kind: 'ol',
      start: 2,
      lines: ['**In Stanza 1.08 (`p2`)**: <img src=x onerror=alert(1)> [bad](javascript:alert(1))'],
    },
  ]);
});

it('answers-1 inlineOf: bold, http(s) links only, backticks dropped', () => {
  expect(inlineOf('**a** `b` [F](https://x.fi/1) [J](javascript:void)')).toEqual([
    { kind: 'b', text: 'a' },
    { kind: 'text', text: ' b ' },
    { kind: 'a', text: 'F', href: 'https://x.fi/1' },
    { kind: 'text', text: ' ' },
    { kind: 'text', text: 'J' },
  ]);
});

it('answers-1 = edits-8 the card shows no raw Markdown, links the law in a new tab, injects no HTML', () => {
  const { container } = card({ ...answerTurn, answers: [], text: LAW_TEXT });
  const text = container.querySelector('.ag-text') as HTMLElement;
  expect(text.textContent).not.toMatch(/\*\*|`|\]\(/);
  expect(within(text).getAllByRole('listitem')).toHaveLength(3);
  expect(text.querySelector('b')?.textContent).toBe('Finland (631/2024):');
  const law = within(text).getByRole('link', { name: 'Finlex' });
  expect(law.getAttribute('href')).toBe('https://www.finlex.fi/fi/2024/631');
  expect(law.getAttribute('target')).toBe('_blank');
  expect(law.getAttribute('rel')).toContain('noopener');
  expect(within(text).getByRole('link', { name: /^Source 1/ })).toBeTruthy(); // [n] still a source link
  expect(text.querySelector('img')).toBeNull();
  expect(within(text).queryByRole('link', { name: 'bad' })).toBeNull();
  expect(text.querySelector('ol')?.getAttribute('start')).toBe('2');
});

// lawcheck-2, lawcheck-3, LC-12
const WINDOW_RULE = {
  ...(info.rule_packs?.[0]?.rules[0] as NonNullable<typeof info.rule_packs>[0]['rules'][0]),
  id: 'ch-zh-room-window',
  op: 'room_windows' as const,
  unit: 'count' as const,
};
const infoWithWindows = {
  ...info,
  rule_packs: info.rule_packs?.map((p) =>
    p.id === 'ch-zh' ? { ...p, rules: [...p.rules, WINDOW_RULE] } : p,
  ),
};

async function lawCard(law: LawCheck) {
  mockApi({ [`GET /api/drawings/${DID}`]: drawing, 'GET /api/info': infoWithWindows });
  const turn = { ...lawRoomTurn, edit: { ...proposal, law } };
  render(
    <InfoProvider>
      <TurnCard
        turn={turn}
        projectId={PID}
        project={project}
        pack="ch-zh"
        busy={false}
        onAsk={vi.fn()}
      />
    </InfoProvider>,
  );
  await screen.findByRole('region', { name: 'Building rules · Canton of Zürich' });
  return within(screen.getByRole('list', { name: 'Rule checks' })).getAllByRole('listitem');
}

const window0 = lawZh.findings[0] as LawCheck['findings'][0];

it('lawcheck-3 a count rule names what it counts: "2 windows → 1 window · at least 1 window"', async () => {
  const [row] = await lawCard({
    ...lawZh,
    findings: [{ ...window0, before: { status: 'pass', value: 2 }, change: 'still_passes' }],
  });
  expect(row?.querySelector('.ag-law-values')?.textContent).toBe(
    'Bagno 1.01: 2 windows → 1 window · at least 1 window',
  );
});

it('lawcheck-2 a new room reads "new room: 3.85 m²", and a rule it meets "✓ Meets", not "Meets now"', async () => {
  const area = lawZh.findings[1] as LawCheck['findings'][0];
  const fresh = { status: 'not_applicable' as const, value: null };
  const rows = await lawCard({
    ...lawZh,
    findings: [
      {
        ...area,
        subject: 'Bedroom',
        before: fresh,
        after: { status: 'fail', value: 3.85, why: null },
      },
      { ...window0, subject: 'Bedroom', before: fresh, change: 'now_passes' },
    ],
  });
  expect(rows.map((r) => r.querySelector('.ag-law-values')?.textContent)).toEqual([
    'Bedroom: new room: 3.85 m² · at least 10 m²',
    'Bedroom: new room: 1 window · at least 1 window',
  ]);
  expect(rows[1]?.querySelector('.ag-law-status')?.textContent).toBe('✓ Meets');
});

// robust-7, robust-8, AC-32 / LC-15
function edit() {
  mockApi({
    [`GET /api/drawings/${DID}`]: drawing,
    [`POST /api/projects/${PID}/chat/${editTurn.chat_id}/proposals/${proposal.proposal_id}`]: {
      ...proposal,
      state: 'rejected',
    },
  });
  render(
    <EditCard proposal={{ ...proposal, law: lawZh }} projectId={PID} chatId={editTurn.chat_id} />,
  );
}

it('robust-7 after Reject the focus is on the "Rejected" status, not lost to the page', async () => {
  edit();
  const reject = screen.getByRole('button', { name: 'Reject' });
  reject.focus();
  fireEvent.click(reject);
  const status = await screen.findByRole('status');
  expect(status.textContent).toBe('Rejected');
  expect(document.activeElement).toBe(status);
});

it('robust-8 with reduced motion the plan jumps into view (no smooth scroll)', async () => {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce') }));
  try {
    edit();
    fireEvent.click(
      (await screen.findAllByRole('button', { name: 'Stanza 1.02' }))[0] as HTMLElement,
    );
    expect(scrolled).toHaveBeenCalledWith({ block: 'nearest', behavior: 'auto' });
  } finally {
    vi.unstubAllGlobals();
  }
});

// edits-9, AC-33
it('edits-9 a room is named with its number, as the plan writes it', () => {
  const room = { id: 'R4', type: 'corridor', page: 1, box: [0, 0, 1, 1] };
  expect(roomName({ ...room, label: 'Corridoio', attrs: { number: '1.04' } })).toBe(
    'Corridoio 1.04',
  );
  expect(roomName({ ...room, label: 'Bagno 1.01', attrs: { number: '1.01' } })).toBe('Bagno 1.01');
  expect(roomName(room)).toBe('corridor');
});

// answers-5, AC-30
it('answers-5 the thread survives leaving the chat ("Show it") and the next turn keeps its chat_id', async () => {
  const chat = `POST /api/projects/${PID}/chat`;
  const routes: Record<string, unknown> = {
    [`GET /api/projects/${PID}`]: project,
    ...Object.fromEntries<unknown>(
      project.drawings.flatMap((d) => [
        [`GET /api/drawings/${d.drawing_id}`, drawing],
        [`GET /api/drawings/${d.drawing_id}/model`, model],
      ]),
    ),
    [chat]: answerTurn,
    [`${chat}/stream`]: reply(404, { detail: 'Not Found', code: 'not_found' }), // no stream route: the sync POST (chat-ux #2)
  };
  mockApi(routes);
  const first = render(<AgentChat projectId={PID} query={new URLSearchParams('ask=How big?')} />);
  await screen.findByText(/is 7.56 m²/);
  first.unmount(); // "Show it" goes to the workspace route
  const api = mockApi(routes);
  render(<AgentChat projectId={PID} query={new URLSearchParams('ask=How big?')} />);
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(screen.getByRole('article', { name: 'How big?' })).toBeTruthy();
  // Back keeps ?ask=: not asked again.
  expect(api.calls.filter((c) => c.method === 'POST')).toEqual([]);
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'And the bedroom?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
  await screen.findAllByText(/is 7.56 m²/);
  expect(api.calls.find((c) => c.method === 'POST' && c.url.endsWith('/chat'))?.body).toEqual({
    chat_id: answerTurn.chat_id,
    message: 'And the bedroom?',
  });
});
