import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { App, type Screens } from './App';
import type { ProjectList } from './api';
import { error as errorBody, info, projectList, rulePackFi } from './api/fixtures';
import { InfoProvider, useInfo } from './shell/info';
import logo from './shell/vellum-logo.png';
import { never, mockApi, reply } from './test/mockApi';

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

function ProjectStub({ projectId }: { projectId: string }) {
  const [mount] = useState(() => ++projectMounts);
  return (
    <p>
      project {projectId} mount {mount}
    </p>
  );
}

const stubs: Screens = {
  HomeScreen: () => <p>home screen</p>,
  AccountScreen: () => <p>account screen</p>,
  ProjectScreen: ProjectStub,
  ConflictsScreen: ({ projectId, query }) => (
    <p>
      conflicts {projectId} {query?.get('pack')}
    </p>
  ),
  ProjectChat: ({ projectId, query }) => (
    <p>
      chat {projectId} {query.get('ask')}
    </p>
  ),
  ChecksScreen: ({ projectId, pack }) => <ChecksStub projectId={projectId} pack={pack} />,
  IssuesScreen: ({ projectId, pack }) => (
    <p>
      issues {projectId} {String(pack)}
    </p>
  ),
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
afterEach(cleanup);

describe('shell', () => {
  it('SH-4 a hash change renders the matching screen without a reload', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
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
    const api = mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy();
    expect(screen.getByText('Nothing at #/nope')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Go to the start' }).getAttribute('href')).toBe('#/');
    await screen.findByText(OFFLINE);
    expect(api.calls.every((c) => ['/api/info', '/api/projects'].includes(c.url))).toBe(true);
  });

  it('SH-7 the product name links to the start on every route', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    for (const hash of ['#/', `#/p/${P}`, `#/p/${P}/d/${D}/engineer`, '#/workspaces', '#/nope']) {
      go(hash);
      expect(screen.getByRole('link', { name: 'Vellum' }).getAttribute('href')).toBe('#/');
    }
    await screen.findByText(OFFLINE);
  });

  it('SH-13 on a drawing route the view links point to the views and keep ?q=', async () => {
    window.location.hash = `#/p/${P}/d/${D}/engineer?q=door`;
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(links().map((l) => [l.text, l.href])).toEqual([
      ['Ingest', `#/p/${P}`],
      ['Conflicts', `#/p/${P}/conflicts`],
      ['Issues', `#/p/${P}/issues`],
      ['Chat', `#/p/${P}/chat`],
      ['Surveyor', `#/p/${P}/d/${D}/surveyor?q=door`],
    ]);
    // Tudor 12:46: no Engineer tab; the engineer route still renders.
    expect(screen.queryByRole('link', { name: 'Engineer' })).toBeNull();
    expect(screen.getByText(`engineer ${D}`)).toBeTruthy();
    await screen.findByText(OFFLINE);
  });

  it('SH-56 the view links of each route; at most the current one is marked', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    const marked = () => links().map((l) => [l.text, l.href, l.current]);
    for (const hash of ['#/', '#/workspaces', '#/nope']) {
      go(hash);
      expect(links(), hash).toEqual([]);
    }
    for (const hash of [`#/p/${P}`, `#/p/${P}/f/f1`]) {
      go(hash);
      expect(marked(), hash).toEqual([
        ['Ingest', `#/p/${P}`, 'page'],
        ['Conflicts', `#/p/${P}/conflicts`, null],
        ['Issues', `#/p/${P}/issues`, null],
        ['Chat', `#/p/${P}/chat`, null],
      ]);
    }
    go(`#/p/${P}/conflicts`);
    expect(marked()).toEqual([
      ['Ingest', `#/p/${P}`, null],
      ['Conflicts', `#/p/${P}/conflicts`, 'page'],
      ['Issues', `#/p/${P}/issues`, null],
      ['Chat', `#/p/${P}/chat`, null],
    ]);
    go(`#/p/${P}/d/${D}/surveyor`);
    expect(marked()).toEqual([
      ['Ingest', `#/p/${P}`, null],
      ['Conflicts', `#/p/${P}/conflicts`, null],
      ['Issues', `#/p/${P}/issues`, null],
      ['Chat', `#/p/${P}/chat`, null],
      ['Surveyor', `#/p/${P}/d/${D}/surveyor`, 'page'],
    ]);
    go(`#/p/${P}/d/${D}/engineer`);
    expect(marked().map(([, , current]) => current)).toEqual([null, null, null, null, null]);
    await screen.findByText(OFFLINE);
  });

  it('SH-64 the chat route mounts ProjectChat; header shows Ingest, Conflicts, Chat (current)', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    go(`#/p/${P}/chat`);
    expect(screen.getByText(`chat ${P}`, { exact: false })).toBeTruthy();
    expect(links().map((l) => [l.text, l.href, l.current])).toEqual([
      ['Ingest', `#/p/${P}`, null],
      ['Conflicts', `#/p/${P}/conflicts`, null],
      ['Issues', `#/p/${P}/issues`, null],
      ['Chat', `#/p/${P}/chat`, 'page'],
    ]);
    await screen.findByText(OFFLINE);
  });

  it('SH-54 account and conflicts mount their screens; ?view does not remount the project', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    go('#/workspaces');
    expect(screen.getByText('account screen')).toBeTruthy();
    go(`#/p/${P}/conflicts`);
    expect(screen.getByText(`conflicts ${P}`, { exact: false })).toBeTruthy();
    go(`#/p/${P}`);
    const first = screen.getByText(new RegExp(`^project ${P} mount`)).textContent;
    go(`#/p/${P}?view=advanced`);
    expect(screen.getByText(new RegExp(`^project ${P} mount`)).textContent).toBe(first);
    await screen.findByText(OFFLINE);
  });

  it('SH-55 the header: logo link, Workspaces link, picker; no country picker or avatar', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    const banner = screen.getByRole('banner');
    const home = within(banner).getByRole('link', { name: 'Vellum' });
    expect(home.getAttribute('href')).toBe('#/');
    expect(home.textContent).toBe('Vellum');
    const img = home.querySelector('img');
    expect(img?.getAttribute('alt')).toBe('');
    expect(img?.getAttribute('src')).toBe(logo);
    expect(banner.querySelectorAll('img')).toHaveLength(1);
    const workspaces = () => within(banner).getByRole('link', { name: 'Workspaces' });
    expect(workspaces().getAttribute('href')).toBe('#/workspaces');
    expect(workspaces().getAttribute('aria-current')).toBeNull();
    expect(within(banner).getByRole('combobox', { name: 'Project' })).toBeTruthy();
    expect(within(banner).queryByText(/Country rules/)).toBeNull();
    go('#/workspaces');
    expect(workspaces().getAttribute('aria-current')).toBe('page');
    go(`#/p/${P}`);
    expect(workspaces().getAttribute('aria-current')).toBeNull();
    await screen.findByText(OFFLINE);
  });

  it('SH-67 checks and issues mount with pack: packOf(route); a ?pack change does not remount', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    go(`#/p/${P}/checks?pack=fi`);
    const first = screen.getByText(new RegExp(`^checks ${P} fi mount`)).textContent;
    go(`#/p/${P}/checks`);
    expect(screen.getByText(new RegExp(`^checks ${P} null mount`)).textContent).toBe(
      first.replace(' fi ', ' null '),
    );
    go(`#/p/${P}/issues?pack=fi`);
    expect(screen.getByText(`issues ${P} fi`)).toBeTruthy();
    go(`#/p/${P}/issues`);
    expect(screen.getByText(`issues ${P} null`)).toBeTruthy();
    go(`#/p/${P}/conflicts?pack=fi`);
    expect(screen.getByText(`conflicts ${P} fi`)).toBeTruthy();
    go(`#/p/${P}/chat?ask=doors`);
    expect(screen.getByText(`chat ${P} doors`)).toBeTruthy();
    await screen.findByText(OFFLINE);
  });

  it('SH-68 with a pack the tabs add Checks and every href carries ?pack', async () => {
    window.location.hash = `#/p/${P}/d/${D}/surveyor?q=door&pack=fi`;
    mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(links().map((l) => [l.text, l.href, l.current])).toEqual([
      ['Ingest', `#/p/${P}?pack=fi`, null],
      ['Conflicts', `#/p/${P}/conflicts?pack=fi`, null],
      ['Checks', `#/p/${P}/checks?pack=fi`, null],
      ['Issues', `#/p/${P}/issues?pack=fi`, null],
      ['Chat', `#/p/${P}/chat?pack=fi`, null],
      ['Surveyor', `#/p/${P}/d/${D}/surveyor?q=door&pack=fi`, 'page'],
    ]);
    go(`#/p/${P}/checks`);
    expect(links().map((l) => [l.text, l.current])).toEqual([
      ['Ingest', null],
      ['Conflicts', null],
      ['Checks', 'page'],
      ['Issues', null],
      ['Chat', null],
    ]);
    go(`#/p/${P}/issues?pack=fi`);
    expect(links().find((l) => l.current)?.text).toBe('Issues');
  });

  it('SH-72 the Checks tab only for a pack info lists (not while info loads); always on its own route', async () => {
    window.location.hash = `#/p/${P}/issues?pack=fi`;
    mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(links().map((l) => l.text)).not.toContain('Checks');
    await screen.findByText(OFFLINE);
    expect(links().map((l) => l.text)).toContain('Checks');
    go(`#/p/${P}/issues?pack=xx`);
    expect(links().map((l) => [l.text, l.href])).toEqual([
      ['Ingest', `#/p/${P}?pack=xx`],
      ['Conflicts', `#/p/${P}/conflicts?pack=xx`],
      ['Issues', `#/p/${P}/issues?pack=xx`],
      ['Chat', `#/p/${P}/chat?pack=xx`],
    ]);
    go(`#/p/${P}/checks?pack=xx`);
    expect(links().find((l) => l.text === 'Checks')?.current).toBe('page');
  });

  it('SH-68 the project picker keeps ?pack', async () => {
    window.location.hash = `#/p/${P}/checks?pack=fi`;
    const other = { ...projectList.projects[0], id: 'aaaaaaaaaaaa', name: 'second.zip' };
    mockApi({
      'GET /api/info': info,
      'GET /api/projects': { projects: [...projectList.projects, other] },
    });
    render(<App screens={stubs} />);
    await screen.findByRole('option', { name: /^second\.zip/ });
    fireEvent.change(screen.getByRole('combobox', { name: 'Project' }), {
      target: { value: other.id },
    });
    expect(window.location.hash).toBe(`#/p/${other.id}?pack=fi`);
  });

  it('SH-69 the country picker lists the rule packs and writes ?pack; no request, no pending', async () => {
    window.location.hash = `#/p/${P}/d/${D}/surveyor?q=door`;
    const api = mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList });
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
    fireEvent.click(fi);
    expect(window.location.hash).toBe(`#/p/${P}/d/${D}/surveyor?q=door&pack=fi`);
    go(window.location.hash);
    expect(button().getAttribute('aria-label')).toBe('Country rules: Finland');
    expect(screen.queryByRole('group', { name: 'Building rules the agent follows' })).toBeNull();
    fireEvent.click(button());
    expect(within(group()).getByText(rulePackFi.note)).toBeTruthy();
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
    expect(document.activeElement).toBe(button());
    expect(api.calls.length).toBe(before);
  });

  it('SH-69 the picker is not rendered off project routes, without packs, or while info loads', async () => {
    mockApi({ 'GET /api/info': withPacks, 'GET /api/projects': projectList });
    const { unmount } = render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    for (const hash of ['#/', '#/workspaces', '#/nope']) {
      go(hash);
      expect(screen.queryByRole('button', { name: /^Country rules/ }), hash).toBeNull();
    }
    go(`#/p/${P}`);
    expect(screen.getByRole('button', { name: /^Country rules/ })).toBeTruthy();
    unmount();
    mockApi({ 'GET /api/info': noPacks, 'GET /api/projects': projectList });
    const second = render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    expect(screen.queryByRole('button', { name: /^Country rules/ })).toBeNull();
    second.unmount();
    mockApi({ 'GET /api/info': never(), 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(screen.queryByRole('button', { name: /^Country rules/ })).toBeNull();
  });

  it('SH-69 src/shell/pending.ts is gone', () => {
    expect(Object.keys(import.meta.glob('./shell/pending.ts'))).toEqual([]);
  });

  it('SH-15 GET /api/info is sent once, not on route changes', async () => {
    const api = mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    await screen.findByText(OFFLINE);
    go(`#/p/${P}`);
    go(`#/p/${P}/d/${D}/engineer`);
    expect(api.calls.filter((c) => c.url === '/api/info')).toHaveLength(1);
  });

  it('SH-16 the offline text shows on home, project, file, workspace and not-found', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
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
    mockApi({ 'GET /api/info': never(), 'GET /api/projects': projectList });
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
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    go(`#/p/${P}`);
    expect(document.activeElement?.id).toBe('main');
    await screen.findByText(OFFLINE);
  });
});

const other = { ...projectList.projects[0], id: 'aaaaaaaaaaaa', name: 'second.zip' };
const two = { projects: [...projectList.projects, other] } as ProjectList;

function picker() {
  return screen.getByRole<HTMLSelectElement>('combobox', { name: 'Project' });
}

describe('project picker', () => {
  it('SH-8 lists the project with its name and creation time', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    await screen.findByRole('option', { name: 'sample-project.zip · 2026-11-14 08:00 UTC' });
  });

  it('SH-9 the route project is selected; choosing another opens it', async () => {
    window.location.hash = `#/p/${P}`;
    mockApi({ 'GET /api/info': info, 'GET /api/projects': two });
    render(<App screens={stubs} />);
    await screen.findByRole('option', { name: /^second\.zip/ });
    expect(picker().value).toBe(P);
    fireEvent.change(picker(), { target: { value: other.id } });
    expect(window.location.hash).toBe(`#/p/${other.id}`);
  });

  it('SH-10 a route project missing from the list asks for the list again, once', async () => {
    const api = mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    await screen.findByRole('option', { name: /^sample-project/ });
    go('#/p/bbbbbbbbbbbb');
    await waitFor(() => {
      expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(2);
    });
    go('#/p/bbbbbbbbbbbb/f/f1');
    go(`#/p/${P}`);
    await screen.findByText(OFFLINE);
    expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(2);
  });

  it('SH-11 loading, empty and error states, and Retry', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': never() });
    const { unmount } = render(<App screens={stubs} />);
    expect(picker().disabled).toBe(true);
    expect(picker().textContent).toBe('Loading projects…');
    unmount();
    mockApi({ 'GET /api/info': info, 'GET /api/projects': { projects: [] } });
    const second = render(<App screens={stubs} />);
    await screen.findByRole('option', { name: 'No projects yet' });
    expect(picker().disabled).toBe(true);
    second.unmount();
    let fail = true;
    const api = mockApi({
      'GET /api/info': info,
      'GET /api/projects': () => {
        const answer = fail
          ? reply(500, { detail: 'internal error', code: 'internal' })
          : projectList;
        fail = false;
        return answer;
      },
    });
    render(<App screens={stubs} />);
    await screen.findByText('Projects: internal error (internal)');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await screen.findByRole('option', { name: /^sample-project/ });
    expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(2);
  });

  it('SH-12 a project name renders as text, never HTML', async () => {
    const name = '<img src=x onerror=alert(1)>';
    const list = { projects: [{ ...projectList.projects[0], name }] } as ProjectList;
    mockApi({ 'GET /api/info': info, 'GET /api/projects': list });
    const { container } = render(<App screens={stubs} />);
    await screen.findByRole('option', { name: `${name} · 2026-11-14 08:00 UTC` });
    expect(container.querySelector('img:not(.brand-logo)')).toBeNull();
  });
});

describe('info strip', () => {
  it('SH-17 with keys there is no offline text, and What runs stays', async () => {
    mockApi({ 'GET /api/info': { ...info, no_keys: false }, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    await screen.findByText('What runs');
    expect(screen.queryByText(OFFLINE)).toBeNull();
  });

  it('SH-18 What runs lists every port with its label and reader', async () => {
    const readers = { ...info.readers, new_port: 'thing' };
    mockApi({ 'GET /api/info': { ...info, readers }, 'GET /api/projects': projectList });
    const { container } = render(<App screens={stubs} />);
    await screen.findByText('What runs');
    const rows = Array.from(container.querySelectorAll('.what-runs dl > div')).map((row) => [
      row.querySelector('dt')?.textContent,
      row.querySelector('dd')?.textContent,
    ]);
    expect(rows).toHaveLength(11);
    expect(rows).toContainEqual(['CAD (DXF)', 'not read']);
    expect(rows).toContainEqual(['Scans and photos', 'not read']);
    expect(rows).toContainEqual(['Vector PDF', 'PDF vector reader']);
    expect(rows).toContainEqual(['Questions', 'question templates']);
    expect(rows).toContainEqual(['Photo rectifier', 'none']);
    expect(rows).toContainEqual(['photo/sheet check', 'off']);
    expect(rows).toContainEqual(['new_port', 'thing']);
  });

  it('R2-qa-3-3 (SH-18) decisions_kind reads photo/sheet check: on / off', async () => {
    mockApi({
      'GET /api/info': { ...info, readers: { ...info.readers, decisions_kind: 'True' } },
      'GET /api/projects': projectList,
    });
    const { container } = render(<App screens={stubs} />);
    await screen.findByText('What runs');
    const row = Array.from(container.querySelectorAll('.what-runs dl > div')).find(
      (r) => r.querySelector('dt')?.textContent === 'photo/sheet check',
    );
    expect(row?.querySelector('dd')?.textContent).toBe('on');
  });
});
