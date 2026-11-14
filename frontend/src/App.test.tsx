import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { App, type Screens } from './App';
import type { ProjectList } from './api';
import { error as errorBody, info, projectList } from './api/fixtures';
import { InfoProvider, useInfo } from './shell/info';
import { never, mockApi, reply } from './test/mockApi';

const P = '5e0c1a2b3d4f';
const D = 'adeefbbcc17559fc';
const OFFLINE = 'Running offline: no API keys, no models';

const stubs: Screens = {
  HomeScreen: () => <p>home screen</p>,
  ProjectScreen: ({ projectId }) => <p>project {projectId}</p>,
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
    expect(screen.getByText(`project ${P}`)).toBeTruthy();
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
    for (const hash of ['#/', `#/p/${P}`, `#/p/${P}/d/${D}/engineer`, '#/nope']) {
      go(hash);
      expect(screen.getByRole('link', { name: 'Countersign' }).getAttribute('href')).toBe('#/');
    }
    await screen.findByText(OFFLINE);
  });

  it('SH-13 on a drawing route the view links point to the three views and keep ?q=', async () => {
    window.location.hash = `#/p/${P}/d/${D}/engineer?q=door`;
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(links().map((l) => [l.text, l.href])).toEqual([
      ['Ingest', `#/p/${P}`],
      ['Engineer', `#/p/${P}/d/${D}/engineer?q=door`],
      ['Surveyor', `#/p/${P}/d/${D}/surveyor?q=door`],
    ]);
    await screen.findByText(OFFLINE);
  });

  it('SH-14 the current view link is marked; project and file show only Ingest; home none', async () => {
    mockApi({ 'GET /api/info': info, 'GET /api/projects': projectList });
    render(<App screens={stubs} />);
    expect(links()).toEqual([]);
    go(`#/p/${P}/d/${D}/surveyor`);
    expect(links().map((l) => [l.text, l.current])).toEqual([
      ['Ingest', null],
      ['Engineer', null],
      ['Surveyor', 'page'],
    ]);
    for (const hash of [`#/p/${P}`, `#/p/${P}/f/f1`]) {
      go(hash);
      expect(links().map((l) => [l.text, l.current])).toEqual([['Ingest', 'page']]);
    }
    go('#/nope');
    expect(links()).toEqual([]);
    await screen.findByText(OFFLINE);
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
    expect(container.querySelector('img')).toBeNull();
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
    expect(rows).toContainEqual(['Vector PDF', 'pdf']);
    expect(rows).toContainEqual(['Photo rectifier', 'none']);
    expect(rows).toContainEqual(['Answer decisions', 'False']);
    expect(rows).toContainEqual(['new_port', 'thing']);
  });
});
