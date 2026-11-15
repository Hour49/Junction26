// Tudor's QA round 4 (board #404), R4-E7: after a send, focus stays in the ask box and the answer is announced.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { drawing, project } from '../api/fixtures';
import { mockApi } from '../test/mockApi';
import { AgentChat } from './AgentChat';
import { answerTurn, model } from './fixtures';

const PID = project.id;
const drawings = Object.fromEntries<unknown>(
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
  sessionStorage.clear();
});

function open() {
  mockApi({
    [`GET /api/projects/${PID}`]: project,
    ...drawings,
    [`POST /api/projects/${PID}/chat`]: answerTurn,
  });
  render(<AgentChat projectId={PID} />);
}

it('R4-E7 Enter in the ask box keeps focus there and announces the answer politely', async () => {
  open();
  const input = await screen.findByLabelText('Question');
  input.focus();
  fireEvent.change(input, { target: { value: 'How big is the bathroom?' } });
  fireEvent.submit(input.closest('form') as HTMLFormElement);
  expect(await screen.findByText(/^Answer ready/)).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByLabelText('Question'));
  const status = screen.getByRole('status', { name: 'Chat status' });
  expect(status.getAttribute('aria-live')).toBe('polite');
  expect(status.textContent).toBe('Answer ready.');
});

it('R4-E7 a tapped starter chip (which unmounts) leaves focus in the ask box', async () => {
  open();
  const group = await screen.findByRole('group', { name: 'Suggested questions' });
  const chip = within(group).getAllByRole('button')[0] as HTMLButtonElement;
  chip.focus();
  fireEvent.click(chip);
  expect(await screen.findByText(/^Answer ready/)).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByLabelText('Question'));
});
