import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { project } from '../api/fixtures';
import type { ProjectView } from '../api';
import { useIssuesToAnswer } from '../shell/issueCount';
import { ConflictsList } from '../surveyor/ConflictsScreen';
import { CONFLICTS_ID, DoneLine, IngestFinished, type ConflictCounts } from './IngestFinished';
import { must, variants } from './testing';

vi.mock('../surveyor/ConflictsScreen', () => ({
  ConflictsList: vi.fn(() => <section id="conflicts">the conflicts list</section>),
}));
vi.mock('../shell/issueCount', () => ({ useIssuesToAnswer: vi.fn(() => null) }));

const ID = project.id;
const listProps = () => must(vi.mocked(ConflictsList).mock.lastCall)[0];
/** What the conflicts list reports, as fe-surveyor's ConflictsList does after a load or a settle. */
function report(counts: ConflictCounts) {
  act(() => {
    must(listProps().onCounts)(counts);
  });
}

afterEach(() => {
  cleanup();
  vi.mocked(ConflictsList).mockClear();
  vi.mocked(useIssuesToAnswer).mockReturnValue(null);
});

describe('IngestFinished and DoneLine (ingest.md v3)', () => {
  it('IN-82 nothing unless done with drawings', () => {
    const notFinished: ProjectView[] = [
      variants.running,
      variants.queued,
      variants.failed,
      variants.noDrawings,
    ];
    for (const p of notFinished) {
      const { container } = render(
        <>
          <DoneLine projectId={ID} project={p} counts={null} />
          <IngestFinished projectId={ID} project={p} />
        </>,
      );
      expect(container.textContent).toBe('');
      cleanup();
    }
    expect(vi.mocked(ConflictsList)).not.toHaveBeenCalled();
    expect(CONFLICTS_ID).toBe('conflicts');
  });

  it('IN-82 renders the conflicts list with the project and the route query; passes its counts up', () => {
    const onCounts = vi.fn();
    const query = new URLSearchParams('d=abc&q=door');
    render(<IngestFinished projectId={ID} project={project} query={query} onCounts={onCounts} />);
    expect(listProps().projectId).toBe(ID);
    expect(listProps().query).toBe(query);
    report({ total: 2, needsPerson: 1 });
    expect(onCounts).toHaveBeenLastCalledWith({ total: 2, needsPerson: 1 });
  });

  it('IN-77 "Start a new chat" waits for every conflict that needs a person; then chat and workspace links', () => {
    render(<IngestFinished projectId={ID} project={project} />);
    const locked = () => {
      const button = screen.getByRole('button', { name: 'Start a new chat' });
      expect((button as HTMLButtonElement).disabled).toBe(true);
      const why = must(document.getElementById(must(button.getAttribute('aria-describedby'))));
      expect(why.textContent).toBe('Settle the conflicts that need you first.');
      expect(screen.queryByRole('link', { name: 'Open the workspace' })).toBeNull();
    };
    locked(); // before the list has loaded
    report({ total: 2, needsPerson: 1 });
    locked();
    report({ total: 2, needsPerson: 0 }); // the last one settled: no reload needed
    expect(screen.queryByRole('button', { name: 'Start a new chat' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Start a new chat' }).getAttribute('href')).toBe(
      `#/p/${ID}/chat`,
    );
    expect(screen.getByRole('link', { name: 'Open the workspace' }).getAttribute('href')).toBe(
      `#/p/${ID}/d/${must(project.drawings[0]).drawing_id}/engineer`,
    );
  });

  it('IN-76 the done line: drawings ready, conflicts below, issues in Documents', () => {
    const line = (counts: ConflictCounts | null, issues: number | null) => {
      vi.mocked(useIssuesToAnswer).mockReturnValue(issues);
      const { container } = render(<DoneLine projectId={ID} project={project} counts={counts} />);
      const text = container.textContent;
      cleanup();
      return text;
    };
    expect(line(null, null)).toBe('5 drawings ready.');
    expect(line({ total: 0, needsPerson: 0 }, 0)).toBe('5 drawings ready.');
    expect(line({ total: 3, needsPerson: 1 }, 2)).toBe(
      '5 drawings ready. Conflicts are below. 2 issues in Documents need you.',
    );
    expect(line({ total: 3, needsPerson: 1 }, 1)).toBe(
      '5 drawings ready. Conflicts are below. 1 issue in Documents needs you.',
    );
    vi.mocked(useIssuesToAnswer).mockReturnValue(2);
    render(<DoneLine projectId={ID} project={project} counts={null} />);
    expect(screen.getByRole('link', { name: '2 issues in Documents' }).getAttribute('href')).toBe(
      `#/p/${ID}/documents`,
    );
    expect(vi.mocked(useIssuesToAnswer)).toHaveBeenCalledWith(ID);
  });
});
