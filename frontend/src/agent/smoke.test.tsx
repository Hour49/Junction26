// Smoke after #309 (.agents/qa-law/rerun2-smoke.md), each test named by its QA id.
import { cleanup, render, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { project } from '../api/fixtures';
import { editTurn } from './fixtures';
import { TurnCard } from './TurnCard';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

const hrefs = (pack: string | null) => {
  const { container } = render(
    <TurnCard
      turn={editTurn}
      projectId={project.id}
      project={project}
      pack={pack}
      busy={false}
      onAsk={vi.fn()}
    />,
  );
  const sources = within(container).getByRole('list', { name: 'Sources' });
  const shows = within(sources).getAllByRole('link', { name: 'Show it' });
  const cites = [...container.querySelectorAll<HTMLAnchorElement>('a.ag-cite')];
  return [...shows, ...cites].map((a) => a.getAttribute('href') ?? '');
};

it("smoke-2 an edit card's Show it and [n] links keep the chat's country", () => {
  const kept = hrefs('ch-zh');
  expect(kept.length).toBeGreaterThan(0);
  for (const href of kept) expect(href).toMatch(/[?&]page=.*&pack=ch-zh/);
  cleanup();
  for (const href of hrefs(null)) expect(href).not.toMatch(/pack=/);
});
