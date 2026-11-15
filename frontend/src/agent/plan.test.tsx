// chat-ux #1: the plan beside the chat, driven by ChatTurn.view (.agents/chat/contract.md A); PageViewer mocked to
// read what it gets.
import type { ComponentProps } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { drawing, info, project } from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { mockApi } from '../test/mockApi';
import type { PageViewer } from '../viewer/PageViewer';
import { KEPT_VERSION } from '../shell/kept';
import { AgentChat } from './AgentChat';
import { paneFocus, viewMarks } from './PlanPane';
import { unionBox, viewOf, type ChatTurn, type View } from './agent';
import { answerTurn, conflictTurn, DID, dontKnowTurn, model } from './fixtures';

type ViewerProps = ComponentProps<typeof PageViewer>;
const viewers: ViewerProps[] = [];
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: ViewerProps) => {
    viewers.push(props);
    // the viewer's own class: the sheet leaves Escape inside it to the viewer
    return (
      <div data-testid="viewer" className="vw" tabIndex={0}>
        {props.file}
      </div>
    );
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
let resizes: (() => void)[] = [];
/** The window crosses 1200 px. */
const resize = (to: boolean) => {
  wide = to;
  act(() => {
    resizes.forEach((f) => {
      f();
    });
  });
};
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  viewers.length = 0;
  wide = true;
  resizes = [];
  vi.unstubAllGlobals();
});

function open(chat: unknown, proj: typeof project = project) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    get matches() {
      return q.includes('min-width') ? wide : false;
    },
    addEventListener: (_: string, f: () => void) => {
      resizes.push(f);
    },
    removeEventListener: vi.fn(),
  }));
  const routes: Record<string, unknown> = { [`GET /api/projects/${PID}`]: proj, [CHAT]: chat };
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

/** A box as the outline polygon the pane sends for a focused source (W1). */
const outline = ([x0, y0, x1, y1]: number[]) => [
  [x0, y0],
  [x1, y0],
  [x1, y1],
  [x0, y1],
];
const pane = () => screen.getByRole('complementary', { name: 'Plan' });
/** The list row of a file, by its name. */
const row = (name: string) =>
  within(pane()).getByRole('heading', { name }).closest('li') as HTMLElement;
const nameButton = (name: string) => within(pane()).getByRole('button', { name });

describe('viewOf', () => {
  it("returns the server's view as sent, null included", () => {
    expect(viewOf(viewTurn)).toBe(shownView);
    expect(viewOf({ ...answerTurn, view: null })).toBeNull();
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

it('W1 the pane never sends a zoom box: the page opens whole, a focused source is an outline', () => {
  // A box focus makes PageViewer zoom in on a small place (2x/4x), cutting the plan off in the narrow pane.
  expect(paneFocus(shownView, null)).toEqual({ page: 1 });
  const f = paneFocus(shownView, [0.31, 0.22, 0.38, 0.29]);
  expect(f).not.toHaveProperty('box');
  expect(f?.polygon).toEqual(outline([0.31, 0.22, 0.38, 0.29]));
  expect(paneFocus(null, null)).toBeNull();
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
    expect(viewer().focus).toEqual({ page: 1 }); // W1: the whole page, no zoom box
    expect(viewer().marks.map((m) => [m.n, m.label, m.polygon?.length])).toEqual([
      [1, 'Bagno 1.01', 4],
    ]);
    // ui-bugs 13: no "Open in workspace" in the pane, neither in its head nor on a file's row
    expect(within(pane()).queryByRole('link', { name: 'Open in workspace' })).toBeNull();
    expect(within(pane()).queryByText('Open in workspace')).toBeNull();
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
    expect(viewer().focus).toEqual({
      page: 1,
      polygon: outline(unionBox([[0.31, 0.22, 0.38, 0.29]])),
    });
  });

  it('a source on another page opens that page with its own mark', async () => {
    open(conflictTurn);
    await send('How many doors?');
    expect(await screen.findByText(/The drawings disagree/)).toBeTruthy();
    await waitFor(() => {
      expect(viewer().focus?.page).toBe(1);
    });
    fireEvent.click(screen.getByRole('link', { name: /^Source 2:/ }));
    expect(viewer().focus).toEqual({ page: 2 });
    expect(viewer().marks.map((m) => m.n)).toEqual([2]);
  });

  it('a turn without a place leaves the plan where it was', async () => {
    let n = 0;
    open(() => (n++ === 0 ? viewTurn : dontKnowTurn));
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    await send('Which walls carry load?');
    expect(await screen.findByText(/does not say which walls carry load/)).toBeTruthy();
    expect(viewer().focus).toEqual({ page: 1 }); // W1: the whole page, no zoom box
  });

  it('a restored thread (back from the workspace) reopens its newest view', async () => {
    // answers-5 keeps the thread in sessionStorage; the older turn has no place, the newest has one
    const kept = {
      v: KEPT_VERSION, // the current kept shape (R4-C13: another version is dropped)
      chatId: viewTurn.chat_id,
      rows: [
        { id: 1, message: 'Where is Bagno 1.01?', chips: [], status: 'done', turn: viewTurn },
        {
          id: 2,
          message: 'Which walls carry load?',
          chips: [],
          status: 'done',
          turn: dontKnowTurn,
        },
      ],
    };
    sessionStorage.setItem(`agent-chat:${PID}`, JSON.stringify(kept));
    open(viewTurn);
    const aside = await screen.findByRole('complementary', { name: 'Plan' });
    expect(within(aside).getByText('Bagno 1.01 on the plan')).toBeTruthy();
    await waitFor(() => {
      expect(within(pane()).getByTestId('viewer')).toBeTruthy();
    });
    expect(viewer().focus).toEqual({ page: 1 }); // W1: the whole page, no zoom box
    expect(viewer().marks.map((m) => m.n)).toEqual([1]);
  });

  it('ui-bugs 2 the empty chat lists the files by name; the first is open, a name opens and closes its plan', async () => {
    open(viewTurn);
    await waitFor(() => {
      expect(within(row('Drawn plan 1')).getByTestId('viewer')).toBeTruthy();
    });
    const names = within(pane())
      .getAllByRole('heading', { level: 3 })
      .map((h) => h.textContent.slice(1)); // after the ▸/▾ mark
    expect(names).toEqual([
      'Drawn plan 1',
      'Drawn plan 2',
      'Drawn plan 3',
      'Plan image 1',
      'Plan photo 1',
      'Building model 1',
    ]);
    expect(nameButton('Drawn plan 1').getAttribute('aria-expanded')).toBe('true');
    // only open files mount a viewer (their pages load on open)
    expect(within(pane()).getAllByTestId('viewer')).toHaveLength(1);
    expect(within(row('Drawn plan 2')).queryByTestId('viewer')).toBeNull();
    fireEvent.click(nameButton('Drawn plan 2'));
    expect(within(row('Drawn plan 2')).getByTestId('viewer')).toBeTruthy();
    expect(within(pane()).getAllByTestId('viewer')).toHaveLength(2); // several open at once
    fireEvent.click(nameButton('Drawn plan 1'));
    expect(nameButton('Drawn plan 1').getAttribute('aria-expanded')).toBe('false');
    expect(within(row('Drawn plan 1')).queryByTestId('viewer')).toBeNull();
    expect(within(row('Drawn plan 2')).getByTestId('viewer')).toBeTruthy();
  });

  it('ui-bugs 2 [n] on a closed file opens it with its marks and scrolls it into view', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    fireEvent.click(nameButton('Drawn plan 1')); // the user closes it
    expect(within(row('Drawn plan 1')).queryByTestId('viewer')).toBeNull();
    // eslint-disable-next-line @typescript-eslint/unbound-method -- the beforeAll mock, read for its calls
    const scroll = vi.mocked(Element.prototype.scrollIntoView);
    scroll.mockClear();
    fireEvent.click(screen.getByRole('link', { name: /^Source 1:/ }));
    expect(within(row('Drawn plan 1')).getByTestId('viewer')).toBeTruthy();
    expect(viewer().marks.map((m) => m.n)).toEqual([1]);
    expect(scroll.mock.contexts).toContain(row('Drawn plan 1'));
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
    fireEvent.keyDown(sheet, { key: 'Escape' });
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
    expect(viewer().focus).toEqual({
      page: 1,
      polygon: outline(unionBox([[0.31, 0.22, 0.38, 0.29]])),
    });
    fireEvent.click(within(sheet).getByRole('button', { name: 'Close' }));
    expect(dialog()).toBeNull();
    expect(cite.getAttribute('href')).toContain(`/d/${DID}`); // a modified click still opens the workspace
  });

  it('Tab stays inside the sheet: from the last control to the first and back', async () => {
    wide = false;
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await screen.findByRole('link', { name: /^Source 1:/ });
    fireEvent.click(screen.getByRole('button', { name: 'Show the plan' }));
    const sheet = dialog() as HTMLElement;
    const all = [...sheet.querySelectorAll<HTMLElement>('a[href], button, [tabindex="0"]')];
    const first = all[0] as HTMLElement;
    const last = all.at(-1) as HTMLElement;
    expect(all.length).toBeGreaterThan(2);
    fireEvent.keyDown(sheet, { key: 'Tab' }); // from the sheet itself, as it opens
    expect(document.activeElement).toBe(first);
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("Escape inside the viewer is the viewer's (a tip, a drag); elsewhere in the sheet it closes it", async () => {
    wide = false;
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await screen.findByRole('link', { name: /^Source 1:/ });
    fireEvent.click(screen.getByRole('button', { name: 'Show the plan' }));
    const sheet = dialog() as HTMLElement;
    fireEvent.keyDown(within(sheet).getByTestId('viewer'), { key: 'Escape' });
    expect(dialog()).toBeTruthy();
    fireEvent.keyDown(within(sheet).getByRole('button', { name: 'Close' }), { key: 'Escape' });
    expect(dialog()).toBeNull();
  });

  it('widening closes the sheet (the pane shows); narrowing again does not reopen it', async () => {
    wide = false;
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await screen.findByRole('link', { name: /^Source 1:/ });
    fireEvent.click(screen.getByRole('button', { name: 'Show the plan' }));
    expect(dialog()).toBeTruthy();
    resize(true);
    expect(dialog()).toBeNull();
    expect(pane()).toBeTruthy();
    resize(false);
    expect(dialog()).toBeNull();
    expect(screen.queryByRole('complementary', { name: 'Plan' })).toBeNull();
  });

  it('R4-F3 the sheet has its own pen ("Draw") beside Close, so drawing does not need the ask bar it covers', async () => {
    wide = false;
    // a drawn PDF can be drawn on (the pen is greyed out on scans, so the sheet has none there)
    open(viewTurn, {
      ...project,
      drawings: project.drawings.map((d) => ({ ...d, drawable: d.route === 'vector' })),
    });
    await send('Where is Bagno 1.01?');
    await screen.findByRole('link', { name: /^Source 1:/ });
    fireEvent.click(screen.getByRole('button', { name: 'Show the plan' }));
    const sheet = dialog() as HTMLElement;
    const pen = within(sheet).getByRole('button', { name: 'Draw' });
    expect(pen.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(pen);
    expect(pen.getAttribute('aria-pressed')).toBe('true');
    expect(dialog()).toBe(sheet); // still open: the plan to draw on is in it
    fireEvent.click(pen);
    expect(pen.getAttribute('aria-pressed')).toBe('false');
  });

  it('a wide window has neither the button nor a Close', async () => {
    open(viewTurn);
    await send('Where is Bagno 1.01?');
    await within(pane()).findByText('Bagno 1.01 on the plan');
    expect(screen.queryByRole('button', { name: 'Show the plan' })).toBeNull();
    expect(within(pane()).queryByRole('button', { name: 'Close' })).toBeNull();
    // the pen stays in the ask bar beside the pane, not twice
    expect(within(pane()).queryByRole('button', { name: 'Draw' })).toBeNull();
  });
});

describe('the plan beside the chat, from the step stream (chat-ux #2, contract C)', () => {
  it("show_on_plan's view event moves the plan while the turn still runs; the answer's view has the last word", async () => {
    const enc = new TextEncoder();
    let ctl!: ReadableStreamDefaultController<Uint8Array>;
    vi.stubGlobal('matchMedia', () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const routes: Record<string, unknown> = {
      'GET /api/info': info, // chat.stream true, as the backend's fixture
      [`GET /api/projects/${PID}`]: project,
    };
    for (const d of project.drawings) {
      routes[`GET /api/drawings/${d.drawing_id}`] = { ...drawing, id: d.drawing_id };
      routes[`GET /api/drawings/${d.drawing_id}/model`] = model;
    }
    const api = mockApi(routes);
    vi.stubGlobal('fetch', (url: string, init?: RequestInit) =>
      url.endsWith('/chat/stream')
        ? Promise.resolve(
            new Response(
              new ReadableStream<Uint8Array>({
                start(c) {
                  ctl = c;
                },
              }),
              { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
            ),
          )
        : api.fetch(url, init),
    );
    render(
      <InfoProvider>
        <AgentChat projectId={PID} />
      </InfoProvider>,
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const push = async (event: string, data: unknown) => {
      await act(async () => {
        ctl.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        await new Promise((r) => setTimeout(r, 0));
      });
    };
    await send('Where is Bagno 1.01?');
    await push('turn', { chat_id: 'c1', turn: 1 });
    await push('view', shownView);
    expect(screen.getByText('Working on it…')).toBeTruthy();
    expect(within(pane()).getByText('Bagno 1.01 on the plan')).toBeTruthy();
    expect(viewer().focus).toEqual({ page: 1 }); // W1: the whole page, no zoom box
    const last = { ...shownView, caption: 'Bagno 1.01, as answered' };
    await push('answer', { ...answerTurn, view: last });
    expect(await within(pane()).findByText('Bagno 1.01, as answered')).toBeTruthy();
  });
});
