// engineer.md "Opening at a question or a place": ?ask= asks on open, ?page=&box= focuses the opening viewer.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { answer, answerRefused, drawing, error, project } from '../api/fixtures';
import { mockApi, never } from '../test/mockApi';
import type { PageViewer } from '../viewer/PageViewer';
import { EngineerPage } from './EngineerPage';

type ViewerProps = ComponentProps<typeof PageViewer> & { focus?: unknown };
const viewers: ViewerProps[] = [];
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: ViewerProps) => {
    viewers.push(props);
    return <div data-testid="viewer" />;
  },
}));

const PROJECT = project.id;
const DRAWING = drawing.id;
const Q = 'How many doors are there?';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  viewers.length = 0;
});

function open(query: string, routes: Parameters<typeof mockApi>[0] = {}, strict = false) {
  const api = mockApi({
    [`GET /api/projects/${PROJECT}`]: project,
    [`GET /api/drawings/${DRAWING}`]: drawing,
    'POST /api/ask': answer,
    ...routes,
  });
  const page = (
    <EngineerPage projectId={PROJECT} drawingId={DRAWING} query={new URLSearchParams(query)} />
  );
  render(strict ? <StrictMode>{page}</StrictMode> : page);
  return api;
}
const posts = (api: ReturnType<typeof mockApi>) => api.calls.filter((c) => c.method === 'POST');
/** The focus the opening card's viewer got last; undefined when it got none. */
const lastFocus = () => viewers.at(-1)?.focus;
const loaded = () => screen.findByRole('textbox', { name: 'Question' });

it('EN-72 ?ask= asks once after the drawing loads (also in StrictMode); the answer shows', async () => {
  const api = open(new URLSearchParams({ ask: Q }).toString(), {}, true);
  const t = await screen.findByRole('article', { name: Q });
  expect((await within(t).findByTestId('answer-value')).textContent).toBe('2');
  expect(posts(api).map((c) => c.body)).toEqual([
    { drawing_id: DRAWING, question: Q, project_id: PROJECT },
  ]);
  // free for the next question: Ask enables as soon as something is typed
  fireEvent.change(screen.getByRole('textbox', { name: 'Question' }), { target: { value: 'x' } });
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' }).disabled).toBe(false);
});

it('EN-73 ?ask= refused: the refusal card with its can_answer chips', async () => {
  open(`ask=${encodeURIComponent(Q)}`, { 'POST /api/ask': { ...answerRefused, question: Q } });
  const t = await screen.findByRole('article', { name: Q });
  expect(await within(t).findByText("I can't answer that from this drawing.")).toBeTruthy();
  for (const c of answerRefused.refusal?.can_answer ?? [])
    expect(within(t).getByRole('button', { name: c.question })).toBeTruthy();
});

it('EN-74 an empty ?ask= or a drawing that fails to load asks nothing', async () => {
  const api = open('ask=%20%20');
  await loaded();
  expect(screen.queryByRole('article')).toBeNull();
  expect(lastFocus()).toBeUndefined();
  cleanup();
  const failed = open(`ask=${encodeURIComponent(Q)}`, {
    [`GET /api/drawings/${DRAWING}`]: { status: 404, body: error },
  });
  await screen.findByRole('link', { name: 'Back to the project' });
  expect(posts(api)).toEqual([]);
  expect(posts(failed)).toEqual([]);
});

it('EN-75 ?q= is not a question here (the surveyor row key): nothing asked', async () => {
  const api = open(`q=${encodeURIComponent(Q)}`);
  await loaded();
  expect(screen.queryByRole('article')).toBeNull();
  expect(posts(api)).toEqual([]);
});

it('EN-76 ?page=&box= focuses the opening viewer; the encoded form too; page alone has box null', async () => {
  open('page=1&box=0.49,0.22,0.51,0.28');
  await loaded();
  expect(lastFocus()).toEqual({ page: 1, box: [0.49, 0.22, 0.51, 0.28] });
  cleanup();
  open(new URLSearchParams({ page: '1', box: '0.49,0.22,0.51,0.28' }).toString());
  await loaded();
  expect(lastFocus()).toEqual({ page: 1, box: [0.49, 0.22, 0.51, 0.28] });
  cleanup();
  open('page=1');
  await loaded();
  expect(lastFocus()).toEqual({ page: 1, box: null });
});

it.each([
  ['page=0', undefined],
  ['page=1.5', undefined],
  ['page=x', undefined],
  ['box=0.1,0.1,0.2,0.2', undefined],
  ['page=9', { page: 9, box: null }],
  ['page=1&box=0.6,0.2,0.5,0.3', { page: 1, box: null }],
  ['page=1&box=0,0,1', { page: 1, box: null }],
  ['page=1&box=0,0,1,1.2', { page: 1, box: null }],
  ['page=1&box=0,0,1,x', { page: 1, box: null }],
])('EN-77 %s gives focus %j', async (query, focus) => {
  open(query);
  await loaded();
  expect(lastFocus()).toEqual(focus);
});

it('EN-77 a building model (no pages) ignores the place', async () => {
  open('page=1&box=0,0,1,1', { [`GET /api/drawings/${DRAWING}`]: { ...drawing, pages: [] } });
  expect(await screen.findByText('Building model: no sheet to draw on.')).toBeTruthy();
  expect(viewers).toEqual([]);
});

it('EN-78 ?ask= with a place: the question is asked, no opening card gets the focus', async () => {
  const api = open(`ask=${encodeURIComponent(Q)}&page=1&box=0,0,1,1`, {
    'POST /api/ask': () => never(),
  });
  await screen.findByRole('article', { name: Q });
  expect(posts(api)).toHaveLength(1);
  expect(viewers.some((v) => v.focus)).toBe(false);
});
