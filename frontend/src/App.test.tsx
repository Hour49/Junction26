import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App, type Screens } from './App';
import type { Issue } from './api';
import {
  error as errorBody,
  info,
  project,
  projectIssues,
  projectList,
  rulePackFi,
} from './api/fixtures';
import { issuesChanged } from './shell/issueCount';
import { INFO_RETRY_MS, InfoProvider, useInfo } from './shell/info';
import logo from './shell/vellum-logo.png';
import { never, mockApi, reply } from './test/mockApi';
import { stubResizeObserver } from './test/resizeObserver';

const P = '5e0c1a2b3d4f';
const D = 'adeefbbcc17559fc';
const OFFLINE = 'Running offline: no API keys, no models';

let projectMounts = 0;
let checksMounts = 0;

function ChecksStub({ projectId, pack }: { projectId: string; pack: string | null }) {
  const [mount] = useState(() => ++checksMounts);
  return (
    <p>
      checks {projectId} {String(pack)} mount {mount}
    </p>
  );
}

const withPacks = info;
const noPacks = { ...info, rule_packs: [] };

function ProjectStub({ projectId, query }: { projectId: string; query?: URLSearchParams }) {
  const [mount] = useState(() => ++projectMounts);
  return (
    <p>
      project {projectId} mount {mount} {query?.toString()}
    </p>
  );
}

let documentsMounts = 0;
function DocumentsStub({ projectId, pack }: { projectId: string; pack: string | null }) {
  const [mount] = useState(() => ++documentsMounts);
  return (
    <p>
      documents {projectId} {String(pack)} mount {mount}
    </p>
  );
}

/** The header's badge asks for the project's state on project routes; a failed project asks no issues, no badge. */
const noIssues = Object.fromEntries(
  [P, 'aaaaaaaaaaaa', 'bbbbbbbbbbbb'].map((id) => [
    `GET /api/projects/${id}`,
    { ...project, id, state: 'failed' },
  ]),
);

const stubs: Screens = {
  HomeScreen: () => <p>home screen</p>,
  AccountScreen: () => <p>account screen</p>,
  ProjectScreen: ProjectStub,
  ProjectChat: ({ projectId, query }) => (
    <p>
      chat {projectId} {query.get('ask')}
    </p>
  ),
  ChecksScreen: ({ projectId, pack }) => <ChecksStub projectId={projectId} pack={pack} />,
  DocumentsScreen: DocumentsStub,
  FileTraceScreen: ({ fileId }) => <p>trace {fileId}</p>,
  EngineerPage: ({ drawingId }) => <p>engineer {drawingId}</p>,
  SurveyorScreen: ({ drawingId, query }) => (
    <p>
      surveyor {drawingId} {query.get('q')}
    </p>
  ),
};

function go(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

function links() {
  return screen.queryAllByRole('navigation', { name: 'Views' }).flatMap((nav) =>
    Array.from(nav.querySelectorAll('a')).map((a) => ({
      text: a.textContent,
      href: a.getAttribute('href'),
      current: a.getAttribute('aria-current'),
    })),
  );
}

beforeEach(() => {
  window.location.hash = '';
});
// The header's hover tips (components/ui/tip.tsx) need it when focus returns to the country pill.
beforeEach(stubResizeObserver);
afterEach(cleanup);

describe('shell', () => {
  it('SH-4 a hash change renders the matching screen without a reload', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    expect(screen.getByText('home screen')).toBeTruthy();
    go(`#/p/${P}`);
    expect(screen.getByText(new RegExp(`^project ${P} mount`))).toBeTruthy();
    go(`#/p/${P}/f/f2`);
    expect(screen.getByText('trace f2')).toBeTruthy();
    go(`#/p/${P}/d/${D}/engineer`);
    expect(screen.getByText(`engineer ${D}`)).toBeTruthy();
    go(`#/p/${P}/d/${D}/surveyor?q=${encodeURIComponent('area:room|name=küche')}`);
    expect(screen.getByText(`surveyor ${D} area:room|name=küche`)).toBeTruthy();
    await screen.findByText(OFFLINE);
  });

  it('SH-5 an unknown route shows the not-found view and asks for nothing else', async () => {
    window.location.hash = '#/nope';
    const api = mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
    expect(screen.getByText('Nothing at #/nope')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Go to the start' }).getAttribute('href')).toBe('#/');
    await screen.findByText(OFFLINE);
    expect(api.calls.every((c) => ['/api/info', '/api/projects'].includes(c.url))).toBe(true);
  });

  it('SH-7 the product name links to the start on every route', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    for (const hash of ['#/', `#/p/${P}`, `#/p/${P}/d/${D}/engineer`, '#/workspaces', '#/nope']) {
      go(hash);
      expect(screen.getByRole('link', { name: 'Vellum' }).getAttribute('href')).toBe('#/');
    }
    await screen.findByText(OFFLINE);
  });

  it('SH-75 the tabs of each route: Ingest, Chat, Documents; at most the current one is marked', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    const marked = () => links().map((l) => [l.text, l.href, l.current]);
    const tabs = (current: string | null) =>
      [
        ['Ingest', `#/p/${P}`],
        ['Chat', `#/p/${P}/chat`],
        ['Documents', `#/p/${P}/documents`],
      ].map(([text, href]) => [text, href, text === current ? 'page' : null]);
    for (const hash of ['#/', '#/workspaces', '#/nope', '#/about']) {
      go(hash);
      expect(links(), hash).toEqual([]);
    }
    for (const hash of [`#/p/${P}`, `#/p/${P}/f/f1`, `#/p/${P}/conflicts`, `#/p/${P}/issues`]) {
      go(hash);
      expect(marked(), hash).toEqual(tabs('Ingest'));
    }
    go(`#/p/${P}/chat`);
    expect(marked()).toEqual(tabs('Chat'));
    go(`#/p/${P}/documents`);
    expect(marked()).toEqual(tabs('Documents'));
    for (const hash of [
      `#/p/${P}/checks`,
      `#/p/${P}/d/${D}/surveyor`,
      `#/p/${P}/d/${D}/engineer`,
    ]) {
      go(hash);
      expect(marked(), hash).toEqual(tabs(null));
    }
    for (const name of ['Conflicts', 'Issues', 'Checks', 'Surveyor', 'Engineer'])
      expect(screen.queryByRole('link', { name }), name).toBeNull();
    expect(screen.getByText(`engineer ${D}`)).toBeTruthy();
    await screen.findByText(OFFLINE);
  });

  it('SH-75 with a pack every tab href carries it (also an unlisted pack)', async () => {
    window.location.hash = `#/p/${P}/d/${D}/surveyor?q=door&pack=fi`;
    mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(links().map((l) => [l.text, l.href])).toEqual([
      ['Ingest', `#/p/${P}?pack=fi`],
      ['Chat', `#/p/${P}/chat?pack=fi`],
      ['Documents', `#/p/${P}/documents?pack=fi`],
    ]);
    go(`#/p/${P}/chat?pack=xx`);
    expect(links().map((l) => l.href)).toEqual([
      `#/p/${P}?pack=xx`,
      `#/p/${P}/chat?pack=xx`,
      `#/p/${P}/documents?pack=xx`,
    ]);
  });

  it('SH-79 SH-80 no credit line from the shell; the footer links About on every route, with the project', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    const about = () =>
      screen.getByRole('link', { name: 'About and credits' }).getAttribute('href');
    for (const hash of ['#/', '#/workspaces', '#/nope'] as const) {
      go(hash);
      expect(about(), hash).toBe('#/about');
    }
    for (const hash of [`#/p/${P}`, `#/p/${P}/chat`, `#/p/${P}/d/${D}/engineer`]) {
      go(hash);
      expect(about(), hash).toBe(`#/about?project=${P}`);
      expect(document.querySelector('.credit'), hash).toBeNull();
      expect(screen.queryByText(/^Credit:/), hash).toBeNull();
    }
    go(`#/p/${P}/documents`); // Documents has no footer link
    expect(screen.queryByRole('link', { name: 'About and credits' })).toBeNull();
    go('#/about');
    expect(screen.getByRole('heading', { level: 1, name: 'About Vellum' })).toBeTruthy();
    expect(links()).toEqual([]);
    await screen.findByText(OFFLINE);
  });

  it('SH-86 the About page: no footer link to itself', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    window.location.hash = `#/about?project=${P}`;
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(screen.queryByRole('link', { name: 'About and credits' })).toBeNull();
    go('#/about');
    expect(screen.queryByRole('link', { name: 'About and credits' })).toBeNull();
  });

  it('SH-64 the chat route mounts ProjectChat with its query', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    go(`#/p/${P}/chat?ask=doors`);
    expect(screen.getByText(`chat ${P} doors`)).toBeTruthy();
    await screen.findByText(OFFLINE);
  });

  it('SH-54 account mounts its screen; ?view does not remount the project', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    go('#/workspaces');
    expect(screen.getByText('account screen')).toBeTruthy();
    go(`#/p/${P}`);
    const mount = () =>
      /mount \d+/.exec(screen.getByText(new RegExp(`^project ${P} mount`)).textContent)?.[0];
    const first = mount();
    go(`#/p/${P}?view=advanced`);
    expect(mount()).toBe(first);
    await screen.findByText(OFFLINE);
  });

  it('SH-55 the header: logo link; no Workspaces link, project picker, country picker or avatar', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    const banner = screen.getByRole('banner');
    const home = within(banner).getByRole('link', { name: 'Vellum' });
    expect(home.getAttribute('href')).toBe('#/');
    expect(home.textContent).toBe('Vellum');
    const img = home.querySelector('img');
    expect(img?.getAttribute('alt')).toBe('');
    expect(img?.getAttribute('src')).toBe(logo);
    expect(banner.querySelectorAll('img')).toHaveLength(1);
    expect(within(banner).queryByText(/Country rules/)).toBeNull();
    // ui-bugs 10 and 11: earlier projects are on #/workspaces, linked from the home page, not the header.
    for (const hash of ['#/', '#/workspaces', `#/p/${P}`, `#/p/${P}/checks`, '#/about']) {
      go(hash);
      expect(within(banner).queryByRole('link', { name: 'Workspaces' }), hash).toBeNull();
      expect(banner.querySelector('select'), hash).toBeNull();
    }
    await screen.findByText(OFFLINE);
  });

  it('SH-67 SH-76 checks and documents mount with pack: packOf(route); a ?pack change does not remount', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    go(`#/p/${P}/checks?pack=fi`);
    const first = screen.getByText(new RegExp(`^checks ${P} fi mount`)).textContent;
    go(`#/p/${P}/checks`);
    expect(screen.getByText(new RegExp(`^checks ${P} null mount`)).textContent).toBe(
      first.replace(' fi ', ' null '),
    );
    go(`#/p/${P}/documents?pack=fi`);
    const docs = screen.getByText(new RegExp(`^documents ${P} fi mount`)).textContent;
    go(`#/p/${P}/documents`);
    expect(screen.getByText(new RegExp(`^documents ${P} null mount`)).textContent).toBe(
      docs.replace(' fi ', ' null '),
    );
    await screen.findByText(OFFLINE);
  });

  it('SH-77 the old conflicts and issues routes mount the project screen with their query, no remount', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    go(`#/p/${P}`);
    const text = () => screen.getByText(new RegExp(`^project ${P}`)).textContent;
    const mount = () => /mount (\d+)/.exec(text())?.[1];
    const first = mount();
    go(`#/p/${P}/conflicts?d=${D}&q=a`);
    expect(text()).toContain(`d=${D}&q=a`);
    expect(mount()).toBe(first);
    expect(window.location.hash).toBe(`#/p/${P}/conflicts?d=${D}&q=a`);
    go(`#/p/${P}/issues?pack=fi`);
    expect(text()).toContain('pack=fi');
    expect(links().find((l) => l.current)?.text).toBe('Ingest');
    await screen.findByText(OFFLINE);
  });

  it("SH-88 the Documents badge under ?pack counts the pack's issues, not issues_to_answer", async () => {
    const failsRule = {
      ...(projectIssues.issues[0] as Issue),
      id: 'r',
      kind: 'reading_flag' as const,
      severity: 'fails_rule' as const,
      state: 'open' as const,
      answer: null,
    };
    mockApi({
      'GET /api/info': info,
      'GET /api/projects': projectList,
      [`GET /api/projects/${P}`]: { ...project, state: 'done', issues_to_answer: 0 },
      [`GET /api/projects/${P}/issues`]: (c: { url: string }) =>
        c.url.endsWith('?pack=ch-zh') ? { ...projectIssues, issues: [failsRule] } : projectIssues,
    });
    window.location.hash = `#/p/${P}?pack=ch-zh`;
    render(<App screens={stubs} />);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /^Documents/ }).getAttribute('aria-label')).toBe(
        'Documents, 1 issue to answer',
      );
    });
  });

  it('SH-78 SH-87 the Documents badge: the server count, named on the link, refreshed by issuesChanged, gone at 0', async () => {
    let toAnswer = 2;
    const api = mockApi({
      'GET /api/info': info,
      'GET /api/projects': projectList,
      [`GET /api/projects/${P}`]: () => ({ ...project, state: 'done', issues_to_answer: toAnswer }),
    });
    window.location.hash = `#/p/${P}`;
    render(<App screens={stubs} />);
    const tab = () => screen.getByRole('link', { name: /^Documents/ });
    await waitFor(() => {
      expect(tab().getAttribute('aria-label')).toBe('Documents, 2 issues to answer');
    });
    const badge = tab().querySelector('.tab-badge');
    expect(badge?.textContent).toBe('2');
    expect(badge?.getAttribute('aria-hidden')).toBe('true');
    toAnswer = 1;
    act(() => {
      issuesChanged(P);
    });
    await waitFor(() => {
      expect(tab().getAttribute('aria-label')).toBe('Documents, 1 issue to answer');
    });
    toAnswer = 0;
    const asked = () => api.calls.filter((c) => c.url.endsWith(`/projects/${P}`)).length;
    const before = asked();
    go(`#/p/${P}/chat`);
    await waitFor(() => {
      expect(asked()).toBe(before + 1);
    });
    await waitFor(() => {
      expect(tab().querySelector('.tab-badge')).toBeNull();
    });
    expect(tab().getAttribute('aria-label')).toBeNull();
    await screen.findByText(OFFLINE);
  });

  it('SH-69 the country picker lists the rule packs and writes ?pack; no request, no pending', async () => {
    window.location.hash = `#/p/${P}/d/${D}/surveyor?q=door`;
    const api = mockApi({
      'GET /api/info': withPacks,
      'GET /api/projects': projectList,
      ...noIssues,
    });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    const button = () => screen.getByRole('button', { name: /^Country rules: / });
    expect(button().getAttribute('aria-label')).toBe('Country rules: none');
    expect(document.querySelector('[data-pending]')).toBeNull();
    const before = api.calls.length;
    fireEvent.click(button());
    const group = () => screen.getByRole('group', { name: 'Building rules the agent follows' });
    expect(
      within(group()).getByRole('button', { name: 'No checks' }).getAttribute('aria-pressed'),
    ).toBe('true');
    const fi = within(group()).getByRole('button', { name: /^Finland/ });
    expect(fi.textContent).toContain(`${rulePackFi.name} · ${rulePackFi.version}`);
    expect(
      within(group()).getByText('Choose a country to pre-check its building rules.'),
    ).toBeTruthy();
    // the rules page link shows only once a country is chosen
    expect(within(group()).queryByRole('link', { name: 'Building construction rules' })).toBeNull();
    fireEvent.click(fi);
    expect(window.location.hash).toBe(`#/p/${P}/d/${D}/surveyor?q=door&pack=fi`);
    go(window.location.hash);
    expect(button().getAttribute('aria-label')).toBe('Country rules: Finland');
    expect(screen.queryByRole('group', { name: 'Building rules the agent follows' })).toBeNull();
    fireEvent.click(button());
    expect(within(group()).queryByText(rulePackFi.note)).toBeNull();
    expect(
      within(group())
        .getByRole('link', { name: 'Building construction rules' })
        .getAttribute('href'),
    ).toBe(`#/p/${P}/checks?pack=fi`);
    expect(
      within(group())
        .getByRole('button', { name: /^Finland/ })
        .getAttribute('aria-pressed'),
    ).toBe('true');
    fireEvent.click(within(group()).getByRole('button', { name: 'No checks' }));
    expect(window.location.hash).toBe(`#/p/${P}/d/${D}/surveyor?q=door`);
    go(window.location.hash);
    fireEvent.click(button());
    fireEvent.keyDown(group(), { key: 'Escape' });
    expect(screen.queryByRole('group', { name: 'Building rules the agent follows' })).toBeNull();
    // Radix hands focus back to the trigger on a 0 ms timer.
    await waitFor(() => {
      expect(document.activeElement).toBe(button());
    });
    // The badge re-reads the project on a pack change (SH-88); the picker itself asks nothing.
    const notBadge = api.calls.slice(before).filter((c) => c.url !== `/api/projects/${P}`);
    expect(notBadge).toEqual([]);
  });

  it('SH-69 the picker is not rendered off project routes, without packs, or while info loads', async () => {
    mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList, ...noIssues });
    const { unmount } = render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    for (const hash of ['#/', '#/workspaces', '#/nope']) {
      go(hash);
      expect(screen.queryByRole('button', { name: /^Country rules/ }), hash).toBeNull();
    }
    go(`#/p/${P}`);
    expect(screen.getByRole('button', { name: /^Country rules/ })).toBeTruthy();
    unmount();
    mockApi({ 'GET /api/info': noPacks, 'GET /api/projects': projectList, ...noIssues });
    const second = render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(screen.queryByRole('button', { name: /^Country rules/ })).toBeNull();
    second.unmount();
    mockApi({ 'GET /api/info': never(), 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    expect(screen.queryByRole('button', { name: /^Country rules/ })).toBeNull();
  });

  it('SH-69 src/shell/pending.ts is gone', () => {
    expect(Object.keys(import.meta.glob('./shell/pending.ts'))).toEqual([]);
  });

  it('SH-15 GET /api/info is sent once, not on route changes', async () => {
    const api = mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    go(`#/p/${P}`);
    go(`#/p/${P}/d/${D}/engineer`);
    expect(api.calls.filter((c) => c.url === '/api/info')).toHaveLength(1);
  });

  it('SH-16 the offline text shows on home, project, file, workspace and not-found', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    for (const hash of [
      `#/p/${P}`,
      `#/p/${P}/f/f1`,
      `#/p/${P}/d/${D}/engineer`,
      `#/p/${P}/d/${D}/surveyor`,
      '#/nope',
    ]) {
      go(hash);
      expect(screen.getByText(OFFLINE)).toBeTruthy();
    }
  });

  it('SH-19 while info is pending the strip says so and the screen is already there', () => {
    mockApi({ 'GET /api/info': never(), 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    expect(screen.getByRole('status').textContent).toBe('Checking the server…');
    expect(screen.getByText('home screen')).toBeTruthy();
  });

  it('SH-20 an info error shows detail and code, and Retry asks again', async () => {
    let first = true;
    const api = mockApi({
      'GET /api/info': () => {
        const answer = first ? reply(500, errorBody) : info;
        first = false;
        return answer;
      },
      'GET /api/projects': projectList,
      ...noIssues,
    });
    render(<App screens={stubs} />);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(
      'The server did not answer: no drawing 0123456789abcdef (not-found)',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await screen.findByText(OFFLINE);
    expect(api.calls.filter((c) => c.url === '/api/info')).toHaveLength(2);
  });

  it('SH-20b after an info error it asks again by itself, and the strip clears once the server answers', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      let first = true;
      const api = mockApi({
        'GET /api/info': () => {
          const answer = first ? reply(500, errorBody) : info;
          first = false;
          return answer;
        },
        'GET /api/projects': projectList,
        ...noIssues,
      });
      render(<App screens={stubs} />);
      await screen.findByRole('alert');
      await act(() => vi.advanceTimersByTimeAsync(INFO_RETRY_MS));
      await screen.findByText(OFFLINE);
      expect(screen.queryByRole('alert')).toBeNull();
      expect(api.calls.filter((c) => c.url === '/api/info')).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('SH-21 useInfo gives the limits once loaded, null before', async () => {
    mockApi({ 'GET /api/info': info });
    const { result } = renderHook(() => useInfo(), { wrapper: InfoProvider });
    expect(result.current.info).toBeNull();
    await waitFor(() => {
      expect(result.current.info?.limits.upload_mb).toBe(200);
    });
    expect(result.current.info?.limits.question_chars).toBe(2000);
  });

  it('SH-6 on a route change, focus is on main', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    render(<App screens={stubs} />);
    go(`#/p/${P}`);
    expect(document.activeElement?.id).toBe('main');
    await screen.findByText(OFFLINE);
  });
});

describe('info strip', () => {
  it('SH-17 with keys there is no info strip at all: no offline text, no empty bar', async () => {
    mockApi({
      'GET /api/info': { ...info, no_keys: false },
      'GET /api/projects': projectList,
      ...noIssues,
    });
    const { container } = render(<App screens={stubs} />);
    await waitFor(() => {
      expect(container.querySelector('.info-bar')).toBeNull();
    });
    expect(screen.queryByText(OFFLINE)).toBeNull();
    expect(screen.queryByText('What runs')).toBeNull();
  });

  it('SH-18 without keys the strip shows the offline badge only, no "What runs" (ui-bugs 12)', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList, ...noIssues });
    const { container } = render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(screen.queryByText('What runs')).toBeNull();
    expect(container.querySelector('.info-bar details')).toBeNull();
    expect(container.querySelector('.info-bar')?.textContent).toBe(OFFLINE);
  });
});
