// The shared issue card (decision 0018: moved from Documents, which no longer mounts it; the chat asks with it).
// Its tests from the Documents tab (DOC-6..9, DOC-7, DOC-15, RS-30/31, M3-25), re-homed onto the card itself.
import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  drawing,
  error,
  project,
  projectIssues,
  projectTriaged,
  relevanceRequest,
  resolving,
} from '../api/fixtures';
import issueAnswerRequest from '@fixtures/issue_answer_request.json';
import issueAnsweredJson from '@fixtures/issue_answered.json';
import type { FileStatus, Highlight, Issue } from '../api';
import { mockApi, reply } from '../test/mockApi';
import { SourceFigure } from '../viewer/SourceFigure';
import { flush, must } from '../ingest/testing';
import { issueRoute } from '../conflicts/issueLinks';
import { IssueCard } from './IssueCard';

const scene = vi.hoisted(() => ({
  rotate: vi.fn(),
  zoom: vi.fn(),
  reset: vi.fn(),
  dispose: vi.fn(),
  shown: { counts: { affected: 1 }, missing: 0, box: null },
}));
const mount = vi.hoisted(() => vi.fn());
vi.mock('../model3d/scene', () => ({ mount }));
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

/** The card as Documents mounted it: the answered issue replaces the shown one. */
function Holder(props: {
  issue: Issue;
  file?: FileStatus;
  pack?: string | null;
  model?: { fileId: string; highlight: readonly Highlight[] } | null;
  projectId?: string;
}) {
  const [issue, setIssue] = useState(props.issue);
  const [file, setFile] = useState(props.file);
  return (
    <ul>
      <IssueCard
        projectId={props.projectId ?? PID}
        issue={issue}
        n={1}
        drawing={drawing}
        file={file}
        onFile={setFile}
        pack={props.pack ?? null}
        onIssue={setIssue}
        model={props.model}
      />
    </ul>
  );
}
const card = () => within(screen.getByRole('listitem'));

beforeEach(() => {
  localStorage.clear();
  vi.mocked(SourceFigure).mockClear();
});
afterEach(cleanup);

describe('IssueCard', () => {
  it('DOC-3 pill, drawing name (not the path), the file link and why', () => {
    render(<Holder issue={needs} />);
    expect(card().getByText('Needs a person')).toBeTruthy();
    expect(card().getByText('Plan image 1')).toBeTruthy();
    expect(screen.getByRole('listitem').textContent).not.toContain(needs.file);
    expect(card().getByText(needs.why)).toBeTruthy();
    expect(card().getByRole('link', { name: 'Open the file' }).getAttribute('href')).toBe(
      `#/p/${PID}/f/${String(needs.file_id)}`,
    );
  });

  it('DOC-6 the card passes its one source to SourceFigure, minimized', () => {
    render(<Holder issue={needs} />);
    const [props] = must(vi.mocked(SourceFigure).mock.calls.at(-1));
    expect(props.label).toBe('Source of issue 1');
    expect(props.sources[0]?.places).toEqual([
      { label: needs.label, box: needs.box, polygon: needs.polygon },
    ]);
    expect(props.sources[0]?.page).toEqual(drawing.pages.find((p) => p.page === needs.page));
    expect(props.defaultOpen).toBeFalsy();
  });

  it('DOC-9 no chips without suggestions', () => {
    render(<Holder issue={needs} />);
    expect(
      card()
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Use my answer']);
  });

  it('DOC-8 a typed answer: sent with the name, shown, changed, cancelled, undone', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const at = '2026-11-14T08:05:00Z';
    const api = mockApi({
      [ANSWER]: (c: { body: { text?: string; by?: string; undo?: boolean } }) =>
        c.body.undo ? { ...needs, answer: null } : { ...needs, answer: { ...c.body, at } },
    });
    render(<Holder issue={needs} />);
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
    expect(card().getByText(/“1:100” · Ana’s answer, /)).toBeTruthy();
    expect(card().getByText('Answered')).toBeTruthy();
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
    mockApi({ [ANSWER]: reply(500, error) });
    render(<Holder issue={needs} />);
    fireEvent.change(card().getByRole('textbox', { name: 'Your answer' }), {
      target: { value: '1:100' },
    });
    const use = card().getByRole<HTMLButtonElement>('button', { name: 'Use my answer' });
    expect(use.disabled).toBe(true);
    fireEvent.change(card().getByRole('textbox', { name: 'Your name' }), {
      target: { value: 'Ana' },
    });
    fireEvent.click(use);
    await flush();
    expect(card().getByRole('alert').textContent).toContain(`(${error.code})`);
    expect(use.disabled).toBe(false);
  });

  it('DOC-8 with a pack the answer carries it (a code check issue: 404 without)', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const chipped = { ...needs, suggestions: ['Not needed'] };
    const api = mockApi({
      [ANSWER]: {
        ...chipped,
        answer: { text: 'Not needed', by: 'Ana', at: '2026-11-14T08:05:00Z' },
      },
    });
    render(<Holder issue={chipped} pack="fi" />);
    fireEvent.click(card().getByRole('button', { name: 'Not needed' }));
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.url).toBe(
      `/api/projects/${PID}/issues/needs/answer?pack=fi`,
    );
  });

  it('DOC-9 a chip per suggestion sends it as the answer', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const chipped = { ...needs, suggestions: ['Check it on site', 'Not needed'] };
    const api = mockApi({
      [ANSWER]: { ...chipped, answer: (issueAnsweredJson as unknown as Issue).answer },
    });
    render(<Holder issue={chipped} />);
    fireEvent.click(card().getByRole('button', { name: 'Check it on site' }));
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(issueAnswerRequest);
    expect(card().getByText(/“Check it on site” · Ana’s answer/)).toBeTruthy();
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
    const POST = `POST /api/projects/${TID}/files/f3/relevance`;

    it('sends the call with the name, shows the call and Change (undo)', async () => {
      localStorage.setItem(NAME_KEY, 'Ana');
      let undone = false;
      const api = mockApi({
        [POST]: (c: { body: unknown }) => {
          undone = (c.body as { undo?: boolean }).undo === true;
          return undone ? open : site;
        },
      });
      render(<Holder issue={issue} file={open} projectId={TID} />);
      fireEvent.click(card().getByRole('button', { name: 'It belongs to this project' }));
      await flush();
      expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(relevanceRequest);
      expect(card().getByText(/Related to this project: Ana’s call/)).toBeTruthy();
      fireEvent.click(card().getByRole('button', { name: 'Change' }));
      await flush();
      expect(undone).toBe(true);
      expect(card().getByRole('button', { name: 'It does not belong' })).toBeTruthy();
    });

    it('a failed call is worded under the card and the chips work again', async () => {
      localStorage.setItem(NAME_KEY, 'Ana');
      mockApi({ [POST]: reply(409, { ...error, code: 'not-allowed' }) });
      render(<Holder issue={issue} file={open} projectId={TID} />);
      fireEvent.click(card().getByRole('button', { name: 'It does not belong' }));
      await flush();
      expect(card().getByRole('alert').textContent).toBe(
        'The project is still being read: a call can be made once it is done.',
      );
      expect(
        card().getByRole<HTMLButtonElement>('button', { name: 'It does not belong' }).disabled,
      ).toBe(false);
    });
  });

  it('RS-31 Carbon could not tell on a conflict issue, with a link to its card and no form', () => {
    const conflict = issueOf('conflict');
    const said = must(resolving.review.conflicts[0]?.resolved);
    render(
      <Holder issue={{ ...conflict, state: 'open', severity: 'needs_person', resolved: said }} />,
    );
    expect(card().getByText('Needs a person')).toBeTruthy();
    expect(card().getByText('Carbon could not tell')).toBeTruthy();
    expect(card().getByText(said.reason)).toBeTruthy();
    expect(card().getByRole('link', { name: 'Settle the conflict' }).getAttribute('href')).toBe(
      issueRoute(conflict, PID),
    );
    expect(card().queryByRole('textbox')).toBeNull();
  });

  it('decision 0018: children replace the answer form, and no number is shown without n', () => {
    render(
      <IssueCard
        projectId={PID}
        issue={needs}
        drawing={drawing}
        file={undefined}
        onFile={vi.fn()}
        pack={null}
        onIssue={vi.fn()}
      >
        <p>chat choices</p>
      </IssueCard>,
    );
    expect(screen.getByText('chat choices')).toBeTruthy();
    expect(screen.queryByRole('textbox', { name: 'Your answer' })).toBeNull();
    expect(must(vi.mocked(SourceFigure).mock.calls.at(-1))[0].label).toBe('Source of the issue');
  });

  it('DOC-15 the card names no colour literal (Tailwind classes use the theme tokens)', () => {
    const source = readFileSync('src/issues/IssueCard.tsx', 'utf8').replace(
      /\/\/.*|\/\*[\s\S]*?\*\//g,
      '',
    );
    expect(source).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });
});

describe('M3-25 "View in 3D" on the issue card', () => {
  const DOOR: Highlight = { global_id: '19Mfen0Pf4kePiWD$g5Bal', role: 'affected' };
  const check: Issue = {
    ...aside,
    id: 'check-1',
    kind: 'code_check_failed',
    severity: 'fails_rule',
    drawing_id: null,
    drawing_name: 'Drawn plan 1',
    file_id: 'f1',
    page: null,
    box: null,
    model_file_id: 'f2',
    highlight: [DOOR],
  };
  beforeEach(() => {
    mount.mockReset().mockResolvedValue(scene);
  });

  it('opens the model with the checked door; Esc closes, focus back', async () => {
    const api = mockApi({ [`GET /api/projects/${PID}/files/f2/model.glb`]: 'glTF' });
    render(<Holder issue={check} model={{ fileId: 'f2', highlight: [DOOR] }} />);
    const open = card().getByRole('button', { name: 'View in 3D: Drawn plan 1' });
    expect(open.textContent).toBe('View in 3D');
    fireEvent.click(open);
    await flush();
    const dialog = screen.getByRole('dialog', { name: '3D view: Drawn plan 1' });
    expect(api.calls.some((c) => c.url === `/api/projects/${PID}/files/f2/model.glb`)).toBe(true);
    expect(mount.mock.calls[0]?.[2]).toEqual([DOOR]);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /^3D view/ })).toBeNull();
    expect(document.activeElement).toBe(open);
  });

  it('no button without a model', () => {
    render(<Holder issue={check} model={null} />);
    expect(card().queryByRole('button', { name: /in 3D/ })).toBeNull();
  });
});
