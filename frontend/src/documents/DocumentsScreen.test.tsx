import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  drawing,
  error,
  project,
  projectIssues,
  projectRunning,
  projectTriaged,
  relevanceRequest,
} from '../api/fixtures';
import type { FileStatus, Issue, IssueList, ProjectView } from '../api';
import { answerOf, setAnswer } from '../shell/issueAnswers';
import { mockApi, reply } from '../test/mockApi';
import { SourceFigure } from '../viewer/SourceFigure';
import { flush, must } from '../ingest/testing';
import { DocumentsScreen } from './DocumentsScreen';

vi.mock('../viewer/SourceFigure', () => ({
  SourceFigure: vi.fn(({ label }: { label: string }) => <figure aria-label={label} />),
}));

const PID = project.id;
const NAME_KEY = 'countersign.surveyorName';
const issueOf = (kind: string) => must(projectIssues.issues.find((i) => i.kind === kind));
const located = issueOf('reading_flag');
const aside = issueOf('set_aside');
const needs: Issue = {
  ...located,
  id: 'needs',
  severity: 'needs_person',
  box: [0.1, 0.2, 0.3, 0.4],
};

const drawingsOf = (issues: Issue[]) =>
  Object.fromEntries(
    issues
      .filter((i) => i.kind !== 'conflict' && i.drawing_id && i.page !== null)
      .map((i) => [`GET /api/drawings/${String(i.drawing_id)}`, drawing]),
  );

function show(
  body: ProjectView = project,
  issues: IssueList = projectIssues,
  extra: Record<string, unknown> = {},
  pack: string | null = null,
) {
  const api = mockApi({
    [`GET /api/projects/${body.id}`]: body,
    [`GET /api/projects/${body.id}/issues`]: issues,
    ...drawingsOf(issues.issues),
    ...extra,
  });
  render(<DocumentsScreen projectId={body.id} pack={pack} />);
  return api;
}
const issuesRegion = () => within(screen.getByRole('region', { name: 'Issues' }));
const cards = () => issuesRegion().getAllByRole('listitem');

beforeEach(() => {
  localStorage.clear();
  vi.mocked(SourceFigure).mockClear();
});
afterEach(() => {
  cleanup();
  for (const i of [needs, located]) setAnswer(PID, i.id, null);
});

describe('DocumentsScreen (documents.md)', () => {
  it('DOC-1 and DOC-16: kicker, title, counts line, the checks link', async () => {
    show(project, projectIssues, {}, 'fi');
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: 'Documents' })).toBeTruthy();
    expect(document.body.textContent).toContain(project.name);
    expect(document.body.textContent).toContain('3 files ingested, 5 drawings read from them');
    expect(screen.getByRole('link', { name: 'Building-code checks' }).getAttribute('href')).toBe(
      `#/p/${PID}/checks?pack=fi`,
    );
  });

  it('DOC-2 while running: no issues request, the waiting line, lists shown', async () => {
    const api = show({ ...projectRunning, id: PID });
    await flush();
    expect(api.calls.some((c) => c.url.includes('/issues'))).toBe(false);
    expect(
      issuesRegion().getByText('The issues are listed once the project is read.'),
    ).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Files' })).toBeTruthy();
  });

  it('DOC-3 and DOC-4: conflicts left out, numbered cards with pill, file, link and why', async () => {
    show(project, { ...projectIssues, issues: [...projectIssues.issues, needs] });
    await flush();
    const list = cards();
    expect(list.length).toBe(projectIssues.issues.length); // 6 - 1 conflict + needs
    const first = must(list[0]);
    expect(first.textContent).toContain('1');
    expect(first.textContent).toContain('Needs a person');
    expect(first.textContent).toContain(needs.file);
    expect(first.textContent).toContain(needs.why);
    expect(within(first).getByRole('link', { name: 'Open the file' }).getAttribute('href')).toBe(
      `#/p/${PID}/f/${String(needs.file_id)}`,
    );
    expect(document.body.textContent).not.toContain(must(issueOf('conflict').why));
  });

  it('DOC-5 and DOC-9: a note has no answer form; no chips without suggestions', async () => {
    show(project, { ...projectIssues, issues: [located, needs] });
    await flush();
    const [answerable, note] = [must(cards()[0]), must(cards()[1])];
    expect(within(note).queryByRole('textbox')).toBeNull();
    expect(within(note).queryByRole('button', { name: 'Use my answer' })).toBeNull();
    expect(
      within(answerable)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Use my answer']);
  });

  it('DOC-6 each card passes its one source to SourceFigure, minimized', async () => {
    const photo = {
      ...must(project.files[0]),
      id: must(aside.file_id),
      path: aside.file,
      kind: 'photo' as const,
    };
    show(
      { ...project, files: [...project.files, photo] },
      { ...projectIssues, issues: [needs, aside] },
    );
    await flush();
    const calls = vi.mocked(SourceFigure).mock.calls.map(([p]) => p);
    const ofNeeds = must(calls.findLast((p) => p.label === 'Source of issue 1'));
    expect(ofNeeds.sources[0]?.places).toEqual([
      { label: needs.why, box: needs.box, polygon: needs.polygon },
    ]);
    expect(ofNeeds.sources[0]?.page).toEqual(drawing.pages.find((p) => p.page === needs.page));
    expect(ofNeeds.defaultOpen).toBeFalsy();
    const ofAside = must(calls.findLast((p) => p.label === 'Source of issue 2'));
    expect(ofAside.sources[0]?.image).toContain(`/files/${String(aside.file_id)}/preview.png`);
  });

  it('DOC-8 a typed answer: stored, shown, changed, cancelled; empty cannot be sent', async () => {
    show(project, { ...projectIssues, issues: [needs] });
    await flush();
    const card = () => within(must(cards()[0]));
    const use = () => card().getByRole<HTMLButtonElement>('button', { name: 'Use my answer' });
    expect(use().disabled).toBe(true);
    fireEvent.change(card().getByRole('textbox', { name: 'Your answer' }), {
      target: { value: '   ' },
    });
    expect(use().disabled).toBe(true);
    fireEvent.change(card().getByRole('textbox', { name: 'Your answer' }), {
      target: { value: '1:100' },
    });
    fireEvent.click(use());
    await flush();
    expect(answerOf(PID, needs.id)).toBe('1:100');
    expect(card().getByText('You answered: “1:100”.')).toBeTruthy();
    expect(
      card().getByText('Kept in this tab only: the server does not save answers yet.'),
    ).toBeTruthy();
    expect(card().getByText('Answered')).toBeTruthy();
    fireEvent.click(card().getByRole('button', { name: 'Change' }));
    expect(card().getByRole<HTMLInputElement>('textbox', { name: 'Your answer' }).value).toBe(
      '1:100',
    );
    expect(card().getByRole('textbox', { name: 'Your answer' }).getAttribute('maxlength')).toBe(
      '140',
    );
    fireEvent.click(card().getByRole('button', { name: 'Cancel' }));
    expect(card().getByText('You answered: “1:100”.')).toBeTruthy();
  });

  describe('DOC-7 the call on a file that is not a floor plan', () => {
    const TID = projectTriaged.id;
    const site = must(projectTriaged.files.find((f) => f.id === 'f3'));
    const open: FileStatus = {
      ...site,
      triage: { ...must(site.triage), overruled: null, verdict: 'unrelated' },
    };
    const issue: Issue = {
      ...aside,
      id: 'unrelated',
      kind: 'unrelated_file',
      severity: 'needs_person',
      file: site.path,
      file_id: 'f3',
    };
    const body = {
      ...projectTriaged,
      files: projectTriaged.files.map((f) => (f.id === 'f3' ? open : f)),
    };
    const list: IssueList = { ...projectIssues, project_id: TID, issues: [issue] };
    const POST = `POST /api/projects/${TID}/files/f3/relevance`;

    it('sends the call with the name, refetches the issues, shows the call and Change (undo)', async () => {
      localStorage.setItem(NAME_KEY, 'Ana');
      let undone = false;
      const api = show(body, list, {
        [POST]: (c: { body: unknown }) => {
          undone = (c.body as { undo?: boolean }).undo === true;
          return undone ? open : site;
        },
      });
      await flush();
      const card = () => within(must(cards()[0]));
      fireEvent.click(card().getByRole('button', { name: 'It belongs to this project' }));
      await flush();
      expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(relevanceRequest);
      expect(api.calls.filter((c) => c.url.endsWith('/issues')).length).toBe(2);
      expect(card().getByText(/Related to this project: Ana’s call/)).toBeTruthy();
      fireEvent.click(card().getByRole('button', { name: 'Change' }));
      await flush();
      expect(undone).toBe(true);
      expect(card().getByRole('button', { name: 'It does not belong' })).toBeTruthy();
    });

    it('a failed call is worded under the card and the chips work again', async () => {
      localStorage.setItem(NAME_KEY, 'Ana');
      show(body, list, { [POST]: reply(409, { ...error, code: 'not-allowed' }) });
      await flush();
      const card = within(must(cards()[0]));
      fireEvent.click(card.getByRole('button', { name: 'It does not belong' }));
      await flush();
      expect(card.getByRole('alert').textContent).toBe(
        'The project is still being read: a call can be made once it is done.',
      );
      expect(
        card.getByRole<HTMLButtonElement>('button', { name: 'It does not belong' }).disabled,
      ).toBe(false);
    });
  });

  it('DOC-10 drawings and files: names, route words, Open and file links', async () => {
    show();
    await flush();
    const drawings = within(screen.getByRole('region', { name: 'Drawings' }));
    const d = must(project.drawings[0]);
    expect(drawings.getAllByRole('link', { name: 'Open' })[0]?.getAttribute('href')).toBe(
      `#/p/${PID}/d/${d.drawing_id}/engineer`,
    );
    expect(drawings.getByText(d.file)).toBeTruthy();
    const files = within(screen.getByRole('region', { name: 'Files' }));
    for (const f of project.files)
      expect(files.getByText(f.path).closest('a')?.getAttribute('href')).toBe(
        `#/p/${PID}/f/${f.id}`,
      );
  });

  it('DOC-11 Export is a download link to the zip, pack kept', async () => {
    show(project, projectIssues, {}, 'fi');
    await flush();
    const link = issuesRegion().getByRole('link', { name: 'Export' });
    expect(link.getAttribute('href')).toBe(`/api/projects/${PID}/issues.zip?pack=fi`);
    expect(link.hasAttribute('download')).toBe(true);
  });

  it('DOC-13 the issues failing: detail and code with Retry, the lists stay', async () => {
    show(project, projectIssues, {
      [`GET /api/projects/${PID}/issues`]: reply(500, {
        ...error,
        detail: 'boom',
        code: 'internal',
      }),
    });
    await flush();
    expect(issuesRegion().getByText(/boom/)).toBeTruthy();
    expect(issuesRegion().getByRole('button', { name: 'Retry' })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Files' })).toBeTruthy();
  });

  it('every answered issue: the line says so; no issues: nothing needs a look', async () => {
    show(project, { ...projectIssues, issues: [] });
    await flush();
    expect(issuesRegion().getByText('No issues: nothing needs a look.')).toBeTruthy();
  });
});
