import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  drawing,
  error,
  project,
  projectIssues,
  projectReviewResolved,
  resolving,
  projectRunning,
  projectTriaged,
  relevanceRequest,
} from '../api/fixtures';
import issueAnswerRequest from '@fixtures/issue_answer_request.json';
import issueAnsweredJson from '@fixtures/issue_answered.json';
import type { FileStatus, Issue, IssueList, ProjectView } from '../api';
import { mockApi, reply } from '../test/mockApi';
import { SourceFigure } from '../viewer/SourceFigure';
import { flush, must, sheet } from '../ingest/testing';
import { issuesChanged } from '../shell/issueCount';
import { issueRoute } from '../surveyor/issueLinks';
import { DocumentsScreen } from './DocumentsScreen';
import { waitsForYou } from './documents';

vi.mock('../shell/issueCount', async (original) => ({
  ...(await original<typeof import('../shell/issueCount')>()),
  issuesChanged: vi.fn(),
}));
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
  suggestions: [],
};
const ANSWER = `POST /api/projects/${PID}/issues/needs/answer`;

const drawingsOf = (issues: Issue[]) =>
  Object.fromEntries(
    issues
      .filter((i) => (i.kind !== 'conflict' || i.resolved) && i.drawing_id && i.page !== null)
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
const issuesRegion = () => within(screen.getByRole('region', { name: 'Issues on demand' }));
const cards = () => issuesRegion().getAllByRole('listitem');

beforeEach(() => {
  localStorage.clear();
  vi.mocked(SourceFigure).mockClear();
});
afterEach(() => {
  cleanup();
});

describe('DocumentsScreen (documents.md)', () => {
  it('DOC-1 and DOC-16: kicker and title, no counts line; the rules link lives in the country picker', async () => {
    show(project, projectIssues, {}, 'fi');
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: 'Documents' })).toBeTruthy();
    expect(document.body.textContent).toContain(project.name);
    expect(document.body.textContent).not.toContain('files ingested');
    expect(screen.queryByRole('link', { name: 'Building-code checks' })).toBeNull();
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
    // Issues on demand: only what waits for an answer now (no conflicts, notes or answered ones)
    const waiting = [...projectIssues.issues, needs].filter(
      (i) => i.kind !== 'conflict' && waitsForYou(i),
    );
    expect(list.length).toBe(waiting.length);
    const first = must(list[0]);
    expect(first.textContent).toContain('1');
    expect(first.textContent).toContain('Needs a person');
    expect(first.textContent).toContain('Plan image 1'); // #229 drawing_name, not the path
    expect(first.textContent).not.toContain(needs.file);
    expect(first.textContent).toContain(needs.why);
    expect(list.find((c) => c.textContent.includes(aside.why))).toBeUndefined(); // a note: not listed
    expect(within(first).getByRole('link', { name: 'Open the file' }).getAttribute('href')).toBe(
      `#/p/${PID}/f/${String(needs.file_id)}`,
    );
    expect(document.body.textContent).not.toContain(must(issueOf('conflict').why));
  });

  it('DOC-5 and DOC-9: a note is not listed; no chips without suggestions', async () => {
    show(project, { ...projectIssues, issues: [located, needs] });
    await flush();
    expect(cards()).toHaveLength(1); // the note (located) is not listed
    expect(
      within(must(cards()[0]))
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
      { ...projectIssues, issues: [needs, { ...aside, severity: 'needs_person' }] },
    );
    await flush();
    const calls = vi.mocked(SourceFigure).mock.calls.map(([p]) => p);
    const ofNeeds = must(calls.findLast((p) => p.label === 'Source of issue 1'));
    expect(ofNeeds.sources[0]?.places).toEqual([
      { label: needs.label, box: needs.box, polygon: needs.polygon },
    ]);
    expect(ofNeeds.sources[0]?.page).toEqual(drawing.pages.find((p) => p.page === needs.page));
    expect(ofNeeds.defaultOpen).toBeFalsy();
    const ofAside = must(calls.findLast((p) => p.label === 'Source of issue 2'));
    expect(ofAside.sources[0]?.image).toContain(`/files/${String(aside.file_id)}/preview.png`);
  });

  it('DOC-8 a typed answer: sent with the name, shown, changed, cancelled, undone', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const at = '2026-11-14T08:05:00Z';
    const api = show(
      project,
      { ...projectIssues, issues: [needs] },
      {
        [ANSWER]: (c: { body: { text?: string; by?: string; undo?: boolean } }) =>
          c.body.undo ? { ...needs, answer: null } : { ...needs, answer: { ...c.body, at } },
      },
    );
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
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({ text: '1:100', by: 'Ana' });
    expect(vi.mocked(issuesChanged)).toHaveBeenCalledWith(PID); // the header badge asks again
    expect(card().getByText(/“1:100” · Ana’s answer, /)).toBeTruthy();
    expect(card().getByText('Answered')).toBeTruthy();
    expect(document.body.textContent).not.toContain('Kept in this tab only');
    fireEvent.click(card().getByRole('button', { name: 'Change' }));
    expect(card().getByRole<HTMLInputElement>('textbox', { name: 'Your answer' }).value).toBe(
      '1:100',
    );
    expect(card().getByRole('textbox', { name: 'Your answer' }).getAttribute('maxlength')).toBe(
      '140',
    );
    fireEvent.click(card().getByRole('button', { name: 'Cancel' }));
    expect(card().getByText(/“1:100” · Ana’s answer/)).toBeTruthy();
    fireEvent.click(card().getByRole('button', { name: 'Undo' }));
    await flush();
    expect(api.calls.filter((c) => c.method === 'POST').at(-1)?.body).toEqual({ undo: true });
    expect(card().getByRole('textbox', { name: 'Your answer' })).toBeTruthy();
    expect(card().queryByText('Answered')).toBeNull();
  });

  it('DOC-8 no name: nothing can be sent; a failed POST is worded, the form usable', async () => {
    show(project, { ...projectIssues, issues: [needs] }, { [ANSWER]: reply(500, error) });
    await flush();
    const card = within(must(cards()[0]));
    fireEvent.change(card.getByRole('textbox', { name: 'Your answer' }), {
      target: { value: '1:100' },
    });
    const use = card.getByRole<HTMLButtonElement>('button', { name: 'Use my answer' });
    expect(use.disabled).toBe(true);
    fireEvent.change(card.getByRole('textbox', { name: 'Your name' }), {
      target: { value: 'Ana' },
    });
    fireEvent.click(use);
    await flush();
    expect(card.getByRole('alert').textContent).toContain(error.detail);
    expect(card.getByRole('alert').textContent).not.toContain(error.code); // R2-C5
    expect(use.disabled).toBe(false);
  });

  it('DOC-8 under ?pack= the answer carries the pack (a code check issue: 404 without)', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const chipped = { ...needs, suggestions: ['Not needed'] };
    const api = show(
      project,
      { ...projectIssues, issues: [chipped] },
      {
        [ANSWER]: {
          ...chipped,
          answer: { text: 'Not needed', by: 'Ana', at: '2026-11-14T08:05:00Z' },
        },
      },
      'fi',
    );
    await flush();
    fireEvent.click(within(must(cards()[0])).getByRole('button', { name: 'Not needed' }));
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.url).toBe(
      `/api/projects/${PID}/issues/needs/answer?pack=fi`,
    );
  });

  it('DOC-9 a chip per suggestion sends it as the answer', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const chipped = { ...needs, suggestions: ['Check it on site', 'Not needed'] };
    const api = show(
      project,
      { ...projectIssues, issues: [chipped] },
      {
        [ANSWER]: { ...chipped, answer: (issueAnsweredJson as unknown as Issue).answer },
      },
    );
    await flush();
    const card = within(must(cards()[0]));
    fireEvent.click(card.getByRole('button', { name: 'Check it on site' }));
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(issueAnswerRequest);
    expect(card.getByText(/“Check it on site” · Ana’s answer/)).toBeTruthy();
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

    it('listed as the backend sends it, a note: answerable, so on the list, but not counted', async () => {
      // triage's set-aside file comes as `unrelated_file` with severity `note` (documents.md: "unrelated_file
      // notes answerable and not counted"); #440's list rule (the badge's count) dropped it
      const note: Issue = { ...issue, severity: 'note' };
      show(body, { ...list, issues: [note] });
      await flush();
      expect(waitsForYou(note)).toBe(false); // the badge does not count it
      expect(cards()).toHaveLength(1);
      expect(
        within(must(cards()[0])).getByRole('button', { name: 'It belongs to this project' }),
      ).toBeTruthy();
      expect(issuesRegion().queryByText('Nothing needs your answer right now.')).toBeNull();
      // nothing counted: no "0 issues need your answer now." above a card that asks for a call (Bogdan, 2026-11-15)
      expect(issuesRegion().queryByText(/need(s)? your answer now/)).toBeNull();
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

  it('FT-25 a file read as a plan whose sheet the model doubts: its row says what it looks like', async () => {
    const f = must(projectTriaged.files[1]);
    const doubted: FileStatus = {
      ...f,
      state: 'ready',
      triage: {
        ...must(f.triage),
        class: 'floor_plan',
        verdict: null,
        sheet: { ...sheet, decision: 'doubt' },
      },
    };
    const body = { ...projectTriaged, files: [doubted] };
    show(body, { ...projectIssues, project_id: body.id, issues: [] });
    await flush();
    const files = screen.getByRole('region', { name: 'Files' });
    expect(files.textContent).toContain(
      'Read as a floor plan · the sheet-kind step says it looks like an elevation',
    );
  });

  it('RS-30 RS-31 Carbon’s pick and can-not-tell on a conflict issue, with a link to its card', async () => {
    const conflict = issueOf('conflict');
    const pick = must(projectReviewResolved.conflicts[0]?.resolved);
    const issues: Issue[] = [
      { ...conflict, id: 'picked', state: 'open', severity: 'note', resolved: pick },
      {
        ...conflict,
        id: 'cannot',
        state: 'open',
        severity: 'needs_person',
        resolved: resolving.review.conflicts[0]?.resolved,
      },
    ];
    show(project, { ...projectIssues, issues });
    await flush();
    // Carbon's pick is a note: it waits for no one, so only the can-not-tell card is listed
    expect(cards()).toHaveLength(1);
    expect(document.body.textContent).not.toContain(pick.reason);
    const cannot = within(must(cards()[0]));
    const card = must(issueRoute(conflict, PID)); // the conflict card on Ingest (fe-surveyor)
    expect(cannot.getByText('Needs a person')).toBeTruthy();
    expect(cannot.getByText('Carbon could not tell')).toBeTruthy();
    expect(cannot.getByText(must(resolving.review.conflicts[0]?.resolved).reason)).toBeTruthy();
    expect(cannot.getByRole('link', { name: 'Settle the conflict' }).getAttribute('href')).toBe(
      card,
    );
    expect(cannot.queryByRole('textbox')).toBeNull();
    expect(issuesRegion().getByText('1 issue needs your answer now.')).toBeTruthy();
  });

  it('DOC-10 drawings and files: names, route words, Open and file links', async () => {
    show();
    await flush();
    const drawings = within(screen.getByRole('region', { name: 'Drawings' }));
    const d = must(project.drawings[0]);
    expect(drawings.getAllByRole('link', { name: 'Open' })[0]?.getAttribute('href')).toBe(
      `#/p/${PID}/d/${d.drawing_id}/engineer`,
    );
    const card = must(drawings.getByText('Drawn plan 1').closest('li'));
    expect(card.querySelector('b')?.textContent).toBe('Drawn plan 1'); // the plain name is the title (#224)
    expect(within(card).getByText(d.file)).toBeTruthy(); // the path stays as the small line
    const files = within(screen.getByRole('region', { name: 'Files' }));
    // DOC-17: no technical line on read files
    for (const f of project.files) expect(files.queryByText(f.reason)).toBeNull();
    for (const f of project.files)
      expect(files.getByText(f.path).closest('a')?.getAttribute('href')).toBe(
        `#/p/${PID}/f/${f.id}`,
      );
  });

  it('DOC-11 no Export link on the issues', async () => {
    show(project, projectIssues, {}, 'fi');
    await flush();
    expect(issuesRegion().queryByRole('link', { name: 'Export' })).toBeNull();
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

  it('R4-B4 R4-E15 a flagged file row says why, and the issues line says the files need a look as Ingest does', async () => {
    show(project, { ...projectIssues, issues: [] });
    await flush();
    const files = within(screen.getByRole('region', { name: 'Files' }));
    const row = must(files.getByText('plans/flat-b.pdf').closest('a'));
    // R4-B7: its one conflict a rule settled; the file stays flagged
    const why = '1 conflict between the two methods (room areas), settled by a rule';
    expect(within(row).getByText(why)).toBeTruthy();
    expect(issuesRegion().getByText('Nothing needs your answer right now.')).toBeTruthy();
    // the same words as the ingest page's summary (routeSummary), so the two pages agree
    expect(
      issuesRegion().getByText('1 flagged file needs a look: why is on its row under Files.'),
    ).toBeTruthy();
  });

  it('R4-B12 an issue answered before (a reload) stays listed, collapsed: Answered, the answer, Change and Undo', async () => {
    const answered: Issue = {
      ...needs,
      answer: { text: 'Accepted as drawn', by: 'Ana', at: '2026-11-15T03:15:57Z' },
    };
    show(project, { ...projectIssues, issues: [answered] });
    await flush();
    const card = must(cards()[0]);
    expect(within(card).getByText('Answered')).toBeTruthy();
    expect(within(card).getByText(/“Accepted as drawn” · Ana’s answer/)).toBeTruthy();
    expect(within(card).getByRole('button', { name: 'Change' })).toBeTruthy();
    expect(within(card).getByRole('button', { name: 'Undo' })).toBeTruthy();
    expect(vi.mocked(SourceFigure)).not.toHaveBeenCalled(); // collapsed: no picture
    expect(issuesRegion().queryByText('Nothing needs your answer right now.')).toBeNull();
    expect(issuesRegion().queryByText(/need.* your answer now/)).toBeNull(); // answered: not counted
  });

  it('no issue waiting: nothing needs your answer right now', async () => {
    show(project, { ...projectIssues, issues: [] });
    await flush();
    expect(issuesRegion().getByText('Nothing needs your answer right now.')).toBeTruthy();
  });
});
