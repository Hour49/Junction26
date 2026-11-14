// chat-ux #1: the plan beside the chat, driven by ChatTurn.view (.agents/chat/contract.md A); PageViewer mocked to
// read what it gets.
import type { ComponentProps } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { drawing, project } from '../api/fixtures';
import { mockApi } from '../test/mockApi';
import type { PageViewer } from '../viewer/PageViewer';
import { AgentChat } from './AgentChat';
import { viewMarks } from './PlanPane';
import { evidenceView, unionBox, viewOf, type ChatTurn, type View } from './agent';
import { answerTurn, conflictTurn, DID, dontKnowTurn, model } from './fixtures';

type ViewerProps = ComponentProps<typeof PageViewer>;
const viewers: ViewerProps[] = [];
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: ViewerProps) => {
    viewers.push(props);
    return <div data-testid="viewer">{props.file}</div>;
  },
}));
const viewer = () => viewers.at(-1) as ViewerProps;

const PID = project.id;
const CHAT = `POST /api/projects/${PID}/chat`;

/** contract.md A's fixture shape on the fixtures' drawing: a room and its door, shown by show_on_plan. */
const shownView: View = {
  drawing_id: DID,
  name: 'Drawn plan 1',
  page: 1,
  box: [0.29, 0.2, 0.4, 0.31],
  marks: [
    {
      n: 1,
      label: 'Bagno 1.01',
      box: [0.31, 0.22, 0.38, 0.29],
      polygon: [
        [0.31, 0.22],
        [0.38, 0.22],
        [0.38, 0.29],
        [0.31, 0.29],
      ],
    },
  ],
  caption: 'Bagno 1.01 on the plan',
  source: 'show_on_plan',
};
const viewTurn = { ...answerTurn, view: shownView } as ChatTurn;

let wide = true;
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  viewers.length = 0;
  wide = true;
  vi.unstubAllGlobals();
});

function open(chat: unknown) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: q.includes('min-width') ? wide : false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  const routes: Record<string, unknown> = { [`GET /api/projects/${PID}`]: project, [CHAT]: chat };
  for (const d of project.drawings) {
    routes[`GET /api/drawings/${d.drawing_id}`] = { ...drawing, id: d.drawing_id };
    routes[`GET /api/drawings/${d.drawing_id}/model`] = model;
  }
  const api = mockApi(routes);
  render(<AgentChat projectId={PID} />);
  return api;
}

async function send(message: string) {
  const input = await screen.findByLabelText('Question');
  fireEvent.change(input, { target: { value: message } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
}

const pane = () => screen.getByRole('complementary', { name: 'Plan' });

describe('viewOf', () => {
  it("returns the server's view as sent, null included", () => {
    expect(viewOf(viewTurn)).toBe(shownView);
    expect(viewOf({ ...answerTurn, view: null } as ChatTurn)).toBeNull();
  });

  it('without a view field: the page of [1] and every source on it, the box their union with a margin', () => {
    // conflictTurn: [1] on page 1, [2] on page 2 of the same drawing
    const v = viewOf(conflictTurn) as View;
    expect(v.drawing_id).toBe(DID);
    expect(v.page).toBe(1);
    expect(v.marks.map((m) => m.n)).toEqual([1]);
    expect(v.box).toEqual([0.08, 0.08, 0.92, 0.92]);
    expect(v.source).toBe('evidence');
  });

  it('no evidence, no view', () => {
    expect(viewOf(dontKnowTurn)).toBeNull();
  });

  it('unionBox clamps to the page', () => {
    expect(unionBox([[0, 0.5, 0.99, 1]])).toEqual([0, 0.48, 1, 1]);
  });
});

it("viewMarks: a mark sent without a polygon (optional in the server's schema) is outlined by its box", () => {
  const bare = { ...(shownView.marks[0] as View['marks'][number]) };
  delete bare.polygon;
  const [m] = viewMarks({ ...shownView, marks: [bare] });
  expect(m?.polygon).toBeNull();
  expect(m?.box).toEqual(bare.box);
});

describe('the plan beside the chat (wide window)', () => {
  it("shows the project's first drawing before any turn, with no marks", async () => {
    open(viewTurn);
    await waitFor(() => {
      expect(within(pane()).getByTestId('viewer')).toBeTruthy();
    });
    expect(within(pane()).getByRole('heading', { name: 'Drawn plan 1' })).toBeTruthy();
    expect(viewer().marks).toEqual([]);
    expect(viewer().focus).toBeNull();
  });

  it('a turn with a view opens its page, draws its marks, focuses its box and shows the caption', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    expect(await within(pane()).findByText('Bagno 1.01 on the plan')).toBeTruthy();
    expect(viewer().focus).toEqual({ page: 1, box: shownView.box });
    expect(viewer().marks.map((m) => [m.n, m.label, m.polygon?.length])).toEqual([
      [1, 'Bagno 1.01', 4],
    ]);
    expect(
      within(pane()).getByRole('link', { name: 'Open in workspace' }).getAttribute('href'),
    ).toContain('box=0.29%2C0.2%2C0.4%2C0.31');
  });

  it('[n] focuses that source on the plan and stays in the chat', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    const cite = await screen.findByRole('link', { name: /^Source 1:/ });
    const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    act(() => {
      cite.dispatchEvent(click);
    });
    expect(click.defaultPrevented).toBe(true);
    expect(viewer().focus).toEqual({ page: 1, box: unionBox([[0.31, 0.22, 0.38, 0.29]]) });
  });

  it('a source on another page opens that page with its own mark', async () => {
    open(conflictTurn);
    await send('How many doors?');
    expect(await screen.findByText(/The drawings disagree/)).toBeTruthy();
    await waitFor(() => {
      expect(viewer().focus?.page).toBe(1);
    });
    fireEvent.click(screen.getByRole('link', { name: /^Source 2:/ }));
    const e = conflictTurn.evidence[1] as ChatTurn['evidence'][number];
    expect(viewer().focus).toEqual({ page: 2, box: evidenceView(e).box });
    expect(viewer().marks.map((m) => m.n)).toEqual([2]);
  });

  it('a turn without a place leaves the plan where it was', async () => {
    let n = 0;
    open(() => (n++ === 0 ? viewTurn : dontKnowTurn));
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    await send('Which walls carry load?');
    expect(await screen.findByText(/does not say which walls carry load/)).toBeTruthy();
    expect(viewer().focus).toEqual({ page: 1, box: shownView.box });
  });

  it('the drawing switcher shows another drawing, and back shows the view again', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    const pick = within(pane()).getByRole('group', { name: 'Drawings' });
    fireEvent.click(within(pick).getByRole('button', { name: 'Drawn plan 2' }));
    expect(within(pane()).getByRole('heading', { name: 'Drawn plan 2' })).toBeTruthy();
    expect(viewer().marks).toEqual([]);
    fireEvent.click(within(pick).getByRole('button', { name: 'Drawn plan 1' }));
    expect(viewer().marks.map((m) => m.n)).toEqual([1]);
  });
});

describe('a narrow window: the plan as a sheet (chat-ux #9)', () => {
  const dialog = () => screen.queryByRole('dialog', { name: 'The plan' });

  it('no plan beside the chat; "Show the plan" opens it over the chat, Escape closes it and focus returns', async () => {
    wide = false;
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await screen.findByRole('link', { name: /^Source 1:/ });
    expect(dialog()).toBeNull();
    const button = screen.getByRole('button', { name: 'Show the plan' });
    button.focus();
    fireEvent.click(button);
    const sheet = dialog() as HTMLElement;
    expect(within(sheet).getByRole('complementary', { name: 'Plan' })).toBeTruthy();
    expect(within(sheet).getByText('Bagno 1.01 on the plan')).toBeTruthy();
    expect(document.activeElement).toBe(sheet);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it('[n] opens the sheet at that place instead of leaving the chat; Close shuts it', async () => {
    wide = false;
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    const cite = await screen.findByRole('link', { name: /^Source 1:/ });
    const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    act(() => {
      cite.dispatchEvent(click);
    });
    expect(click.defaultPrevented).toBe(true);
    const sheet = dialog() as HTMLElement;
    expect(viewer().focus).toEqual({ page: 1, box: unionBox([[0.31, 0.22, 0.38, 0.29]]) });
    fireEvent.click(within(sheet).getByRole('button', { name: 'Close' }));
    expect(dialog()).toBeNull();
    expect(cite.getAttribute('href')).toContain(`/d/${DID}`); // a modified click still opens the workspace
  });

  it('a wide window has neither the button nor a Close', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    expect(screen.queryByRole('button', { name: 'Show the plan' })).toBeNull();
    expect(within(pane()).queryByRole('button', { name: 'Close' })).toBeNull();
  });
});
