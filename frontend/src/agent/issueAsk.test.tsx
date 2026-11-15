// Decision 0018: the chat asks about an open issue before it answers; the answer goes back as issue_answer.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { drawing, project, projectIssues } from '../api/fixtures';
import type { Issue } from '../api';
import { mockApi } from '../test/mockApi';
import { must } from '../ingest/testing';
import { AgentChat } from './AgentChat';
import type { ChatRequest, ChatTurn } from './agent';
import { answerTurn, model } from './fixtures';

vi.mock('../viewer/SourceFigure', () => ({
  SourceFigure: ({ label }: { label: string }) => <figure aria-label={label} />,
}));

const PID = project.id;
const CHAT = `POST /api/projects/${PID}/chat`;
const conflict = must(projectIssues.issues.find((i) => i.kind === 'conflict'));
const issue: Issue = { ...conflict, severity: 'needs_person', state: 'open' };
const askTurn: ChatTurn = {
  ...answerTurn,
  kind: 'ask_issue',
  text: `Before I answer: Drawn plan 2 has an open issue on this. ${issue.why} Which value should I use?`,
  evidence: [],
  answers: [],
  view: null,
  next: [],
  issue,
  options: [
    { label: 'Use 22.4 m² (room outlines)', message: 'Use 22.4 m² (room outlines)', value: 22.4 },
    { label: 'Use 30 m² (printed areas)', message: 'Use 30 m² (printed areas)', value: 30 },
    { label: 'Check it on site', message: 'Check it on site' },
    { label: 'Skip for now', message: 'Skip for now', skip: true },
  ],
};
const drawings = Object.fromEntries<unknown>(
  project.drawings.flatMap((d) => [
    [`GET /api/drawings/${d.drawing_id}`, drawing],
    [`GET /api/drawings/${d.drawing_id}/model`, model],
  ]),
);

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

function open() {
  let n = 0;
  const api = mockApi({
    [`GET /api/projects/${PID}`]: project,
    ...drawings,
    [CHAT]: () => (n++ === 0 ? askTurn : answerTurn),
  });
  render(<AgentChat projectId={PID} />);
  return api;
}
async function ask() {
  fireEvent.change(await screen.findByLabelText('Question'), {
    target: { value: 'How big is the kitchen?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
  return within(await screen.findByRole('form', { name: 'Answer the issue' }));
}
const posts = (api: ReturnType<typeof mockApi>) =>
  api.calls.filter((c) => c.method === 'POST').map((c) => c.body as ChatRequest);

it('shows the issue as the issue card does, with its choices; no name, no pick', async () => {
  open();
  const form = await ask();
  expect(screen.getByText('Needs a person')).toBeTruthy();
  expect(screen.getByText(issue.why)).toBeTruthy();
  expect(screen.getByText(must(issue.drawing_name))).toBeTruthy();
  const pick = form.getByRole<HTMLButtonElement>('button', { name: 'Use 22.4 m² (room outlines)' });
  expect(pick.disabled).toBe(true); // a settle needs the person's name
  expect(form.getByRole<HTMLButtonElement>('button', { name: 'Skip for now' }).disabled).toBe(
    false,
  );
});

it('a picked value goes back as issue_answer with the name, then the answer comes; the card closes', async () => {
  localStorage.setItem('countersign.surveyorName', 'Ana');
  const api = open();
  const form = await ask();
  fireEvent.click(form.getByRole('button', { name: 'Use 22.4 m² (room outlines)' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(posts(api)[1]).toEqual({
    chat_id: askTurn.chat_id,
    message: 'Use 22.4 m² (room outlines)',
    issue_answer: {
      issue_id: issue.id,
      text: 'Use 22.4 m² (room outlines)',
      by: 'Ana',
      skip: false,
      value: 22.4,
    },
  });
  expect(screen.queryByRole('form', { name: 'Answer the issue' })).toBeNull();
});

it('a typed answer and Skip for now', async () => {
  localStorage.setItem('countersign.surveyorName', 'Ana');
  const api = open();
  const form = await ask();
  fireEvent.change(form.getByRole('textbox', { name: 'Your answer' }), {
    target: { value: 'The printed area is old' },
  });
  fireEvent.click(form.getByRole('button', { name: 'Use my answer' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(posts(api)[1]?.issue_answer).toEqual({
    issue_id: issue.id,
    text: 'The printed area is old',
    by: 'Ana',
    skip: false,
  });
});

it('Skip for now sends skip', async () => {
  const api = open();
  const form = await ask();
  fireEvent.click(form.getByRole('button', { name: 'Skip for now' }));
  expect(await screen.findByText(/is 7.56 m²/)).toBeTruthy();
  expect(posts(api)[1]?.issue_answer).toMatchObject({ issue_id: issue.id, skip: true });
});
