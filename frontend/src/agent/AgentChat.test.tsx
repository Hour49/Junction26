import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, fileReadAsPlan, project } from '../api/fixtures';
import { mockApi, never } from '../test/mockApi';
import { AgentChat } from './AgentChat';
import type { ChatRequest } from './agent';
import { answerTurn, dontKnowTurn, model, needsInputTurn } from './fixtures';

const PID = project.id;
const CHAT = `POST /api/projects/${PID}/chat`;
/** The project as the backend now sends it: the drawn PDFs are `drawable`; scans, photos and models say why not. */
const drawable = {
  ...project,
  drawings: project.drawings.map((d) => ({ ...d, drawable: d.route === 'vector' })),
};
const drawings: Record<string, unknown> = Object.fromEntries<unknown>(
  project.drawings.flatMap((d) => [
    [`GET /api/drawings/${d.drawing_id}`, drawing],
    [`GET /api/drawings/${d.drawing_id}/model`, model],
  ]),
);

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear(); // the kept thread (answers-5)
});

function open(chat: unknown, query?: string) {
  const api = mockApi({ [`GET /api/projects/${PID}`]: drawable, ...drawings, [CHAT]: chat });
  render(<AgentChat projectId={PID} query={new URLSearchParams(query)} />);
  return api;
}

async function send(message: string) {
  const input = await screen.findByLabelText('Question');
  fireEvent.change(input, { target: { value: message } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
}

const posts = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.method === 'POST').map((c) => c.body as ChatRequest);

it('AC-30 first turn without chat_id, the next with the returned one; one turn pending at a time', async () => {
  let n = 0;
  const api = open(() => (n++ === 0 ? needsInputTurn : answerTurn));
  await send('Make the bathroom larger');
  expect(await screen.findByText('There are two bathrooms. Which one do you mean?')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Bagno 1.01' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(posts(api)).toEqual([
    { message: 'Make the bathroom larger' },
    {
      chat_id: needsInputTurn.chat_id,
      message: 'Remove the wall between Bagno 1.01 and the bedroom',
    },
  ]);
});

it('AC-30 while a turn is pending the ask button is disabled', async () => {
  open(never());
  await send('How big is the bathroom?');
  expect(await screen.findByText('Working on it…')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Ask' })).toHaveProperty('disabled', true);
});

it('AC-30 a failed turn says why and can be sent again', async () => {
  let n = 0;
  open(() =>
    n++ === 0 ? { status: 500, body: { detail: 'internal error', code: 'internal' } } : answerTurn,
  );
  await send('How big is the bathroom?');
  const alert = await screen.findByRole('alert');
  expect(alert.textContent).toMatch(/internal error/);
  expect(alert.textContent).not.toMatch(/code:/); // R2-C5: no raw code for a person
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
});

/** Puts the pen down on Drawn plan 1 (open first, in the sheet on this narrow window); its stage, 600 × 400 px. */
async function pointer() {
  const pen = await screen.findByRole('button', { name: 'Draw on the plan' });
  await waitFor(() => {
    expect(pen.getAttribute('aria-disabled')).toBeNull(); // drawable once its pages have come
  });
  fireEvent.click(pen);
  const frame = await waitFor(() => {
    const f = document.querySelector('.ag-drawing .vw-frame');
    if (!f) throw new Error('no page yet');
    return f as HTMLElement;
  });
  frame.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 600, height: 400, right: 600, bottom: 400, x: 0, y: 0 }) as DOMRect;
  return frame.parentElement as HTMLElement;
}

it('AC-33 the pen: a dragged area goes with the next message as a chip, then is cleared', async () => {
  const api = open(answerTurn);
  const stage = await pointer();
  fireEvent.pointerDown(stage, { clientX: 60, clientY: 40, pointerType: 'mouse', button: 0 });
  fireEvent.pointerUp(stage, { clientX: 240, clientY: 120, pointerType: 'mouse', button: 0 });
  expect(await screen.findByText('Area on Drawn plan 1, page 1')).toBeTruthy();
  // R4-F1: the finished drag put the pen down by itself, so typing is back
  expect(
    screen.getByRole('button', { name: 'Draw on the plan' }).getAttribute('aria-pressed'),
  ).toBe('false');
  expect(screen.getByLabelText<HTMLInputElement>('Question').disabled).toBe(false);
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  const [body] = posts(api);
  expect(body?.selection).toEqual([
    {
      id: 'sel_1',
      kind: 'region',
      drawing_id: project.drawings[0]?.drawing_id,
      page: 1,
      box: expect.any(Array) as unknown,
    },
  ]);
  expect(screen.queryByRole('button', { name: 'Remove Area on Drawn plan 1, page 1' })).toBeNull();
});

it('AC-33 a click on a room sends its model id and the chip names it', async () => {
  const api = open(answerTurn);
  const stage = await pointer();
  fireEvent.pointerDown(stage, { clientX: 120, clientY: 80, pointerType: 'mouse', button: 0 });
  fireEvent.pointerUp(stage, { clientX: 120, clientY: 80, pointerType: 'mouse', button: 0 });
  expect(await screen.findByText('Room Bagno 1.01')).toBeTruthy(); // the click put the pen down (R4-F1)
  await send('Make this room larger');
  await screen.findByText(/is 7.56 m²/);
  expect(posts(api)[0]?.selection).toEqual([
    expect.objectContaining({ id: 'sel_1', kind: 'room', ref: 'R3', page: 1 }),
  ]);
});

it('CH-45 follow-up chips after an answer (questions not asked yet); none after a dont_know', async () => {
  let n = 0;
  open(() => (n++ === 0 ? answerTurn : dontKnowTurn));
  await send('How many doors are there?');
  await screen.findByText(/is 7.56 m²/);
  const next = screen.getByRole('group', { name: 'Follow-up questions' });
  expect(next.textContent).not.toContain('How many doors are there?');
  expect(next.textContent).toContain('How many windows are there?');
  await send('Is that wall load-bearing?');
  await screen.findByText("I don't know.");
  expect(screen.queryByRole('group', { name: 'Follow-up questions' })).toBeNull();
});

it("#369 the answer's own next chips (at most 3) replace the drawing follow-ups; a click asks its message", async () => {
  const next = [
    { label: 'Show them on the plan', message: 'Show me where they are' },
    { label: 'Which is the largest?', message: 'Which bathroom is the largest?' },
    { label: 'Total area', message: 'What is the total bathroom area?' },
    { label: 'A fourth', message: 'never shown' },
  ];
  const api = open({ ...answerTurn, next });
  await send('How big is the bathroom?');
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  const group = screen.getByRole('group', { name: 'Follow-up questions' });
  expect(
    within(group)
      .getAllByRole('button')
      .map((b) => b.textContent),
  ).toEqual(['Show them on the plan', 'Which is the largest?', 'Total area']);
  fireEvent.click(within(group).getByRole('button', { name: 'Show them on the plan' }));
  await waitFor(() => {
    expect(posts(api).at(-1)).toEqual({
      chat_id: answerTurn.chat_id,
      message: 'Show me where they are',
    });
  });
});

it('#369 a turn without a next field (kept from an older server) gets the drawing follow-ups', async () => {
  open({ ...answerTurn, next: undefined });
  await send('How many doors are there?');
  await screen.findByText(/is 7.56 m²/);
  expect(screen.getByRole('group', { name: 'Follow-up questions' }).textContent).toContain(
    'How many windows are there?',
  );
});

it("LC-11 every turn sends the route's ?pack=; none without one", async () => {
  const api = open(answerTurn, 'pack=ch-zh');
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  await send('And now?');
  await waitFor(() => {
    expect(posts(api)).toHaveLength(2);
  });
  expect(posts(api).map((b) => b.pack)).toEqual(['ch-zh', 'ch-zh']);
  cleanup();
  sessionStorage.clear(); // a new chat, not the kept one
  const bare = open(answerTurn);
  await send('Put a storage room here');
  await screen.findByText(/is 7.56 m²/);
  expect(posts(bare)[0]).not.toHaveProperty('pack');
});

it('ui-bugs 2g no "What I read" on the empty chat; the project name stays as its title', async () => {
  open(answerTurn);
  expect(await screen.findByRole('heading', { level: 1, name: project.name })).toBeTruthy();
  await screen.findByRole('button', { name: 'Draw on the plan' });
  expect(screen.queryByRole('region', { name: 'What I read' })).toBeNull();
  expect(screen.queryByText('What I read')).toBeNull();
});

it('ui-bugs 1 no "Point at the plan" chip; pen on: typing and sending wait; Escape: typing back, chips kept', async () => {
  open(answerTurn);
  const stage = await pointer();
  expect(screen.queryByRole('button', { name: 'Point at the plan' })).toBeNull();
  const input = screen.getByLabelText('Question');
  expect(input).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: 'Ask' })).toHaveProperty('disabled', true);
  fireEvent.pointerDown(stage, { clientX: 60, clientY: 40, pointerType: 'mouse', button: 0 });
  fireEvent.pointerUp(stage, { clientX: 240, clientY: 120, pointerType: 'mouse', button: 0 });
  expect(await screen.findByText('Area on Drawn plan 1, page 1')).toBeTruthy();
  fireEvent.keyDown(document.body, { key: 'Escape' });
  expect(input).toHaveProperty('disabled', false);
  expect(
    screen.getByRole('button', { name: 'Draw on the plan' }).getAttribute('aria-pressed'),
  ).toBe('false');
  expect(screen.getByText('Area on Drawn plan 1, page 1')).toBeTruthy();
  expect(document.querySelector('.ag-drawing')).toBeNull();
});

it('W4 after the first message the project name still shows, above the thread', async () => {
  open(answerTurn);
  await send('How big is the bathroom?');
  await screen.findByText(/is 7.56 m²/);
  const title = screen.getByRole('heading', { level: 1, name: project.name });
  expect(title.className).not.toContain('en-sr'); // visible, not only for screen readers
});

it('ui-bugs 1 the pen click again puts it down too', async () => {
  open(answerTurn);
  await pointer();
  const pen = screen.getByRole('button', { name: 'Draw on the plan' });
  expect(pen.getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(pen);
  expect(pen.getAttribute('aria-pressed')).toBe('false');
  expect(screen.getByLabelText('Question')).toHaveProperty('disabled', false);
});

it('ui-bugs 1 with no reason from the backend the pen says the generic sentence', async () => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  const bare = {
    ...project,
    drawings: project.drawings
      .filter((d) => d.route === 'raster')
      .map((d) => ({ ...d, not_drawable_reason: null })),
  };
  mockApi({ [`GET /api/projects/${PID}`]: bare, ...drawings, [CHAT]: answerTurn });
  render(<AgentChat projectId={PID} />);
  const pen = await screen.findByRole('button', { name: 'Draw on the plan' });
  fireEvent.click(pen);
  expect((await screen.findByRole('tooltip')).textContent).toContain(
    "You can't draw on this plan: it is a photo/scan.",
  );
  vi.unstubAllGlobals();
});

it('ui-bugs 1 on a photo or scan the pen is greyed out and says why on focus; a tap does not draw', async () => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  const photos = { ...project, drawings: project.drawings.filter((d) => d.route === 'raster') };
  const reason = photos.drawings[0]?.not_drawable_reason ?? '';
  expect(reason).not.toBe('');
  mockApi({ [`GET /api/projects/${PID}`]: photos, ...drawings, [CHAT]: answerTurn });
  render(<AgentChat projectId={PID} />);
  const pen = await screen.findByRole('button', { name: 'Draw on the plan' });
  await new Promise((r) => setTimeout(r, 0));
  expect(pen.getAttribute('aria-disabled')).toBe('true');
  fireEvent.click(pen);
  // the backend's own reason, not the generic sentence
  const tip = (await screen.findByRole('tooltip')).textContent;
  expect(tip).toContain(reason);
  expect(tip).not.toContain('Drawing works on drawn PDF plans');
  expect(screen.getByLabelText('Question')).toHaveProperty('disabled', false);
  expect(document.querySelector('.ag-drawing')).toBeNull();
  vi.unstubAllGlobals();
});

it('CH-18 agent chat: a photo read as a plan makes a project with no askable drawing askable', async () => {
  const added = { ...fileReadAsPlan, id: 'f9', path: 'plan.jpg', state: 'queued' as const };
  const before = { ...project, drawings: [] };
  const after = { ...project, files: [...project.files, { ...added, state: 'ready' as const }] };
  let n = 0;
  const api = mockApi({
    [`GET /api/projects/${PID}`]: () => (n++ === 0 ? before : after),
    ...drawings,
    [`POST /api/projects/${PID}/files`]: added,
    [CHAT]: answerTurn,
  });
  render(<AgentChat projectId={PID} />);
  expect(await screen.findByText('No drawing in this project can be asked yet.')).toBeTruthy();
  fireEvent.change(screen.getByTestId('photo-input'), {
    target: { files: [new File(['jpeg'], 'plan.jpg', { type: 'image/jpeg' })] },
  });
  expect(await screen.findByText('Reading plan.jpg…')).toBeTruthy();
  expect(
    await screen.findByText('plan.jpg is read: you can ask about it.', {}, { timeout: 4000 }),
  ).toBeTruthy();
  expect(screen.queryByText('No drawing in this project can be asked yet.')).toBeNull();
  const post = api.calls.find((c) => c.url.startsWith(`/api/projects/${PID}/files`));
  expect(post?.url).toBe(`/api/projects/${PID}/files?name=plan.jpg`);
  await send('How many doors are there?');
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
}, 8000);

it('#425 the photo picker takes TIFF and WebP too, by type and by extension', async () => {
  open(answerTurn);
  const accept = ((await screen.findByTestId('photo-input')).getAttribute('accept') ?? '').split(
    ',',
  );
  for (const kind of ['image/png', 'image/jpeg', 'image/tiff', 'image/webp'])
    expect(accept).toContain(kind);
  for (const ext of ['.tif', '.tiff', '.webp']) expect(accept).toContain(ext);
});

it('QA G2 a thread kept over a reload scrolls to its last turn once the project loads, not the top', async () => {
  open(answerTurn);
  await send('How big is the bathroom?');
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  cleanup(); // the reload: sessionStorage keeps the thread
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  open(answerTurn);
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  await waitFor(() => {
    expect(scrolled).toHaveBeenCalled();
  });
  Element.prototype.scrollIntoView = vi.fn();
});
