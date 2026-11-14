import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { error, info, projectList, projectStarted } from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { uploadTooLarge } from '../shell/limits';
import { mockApi, never, reply } from '../test/mockApi';
import { HomeScreen } from './HomeScreen';
import { flush, must } from './testing';

const LIST = 'GET /api/projects';
const UPLOAD = 'POST /api/projects';
const SAMPLE = 'POST /api/projects/sample';

function input() {
  return must(document.querySelector<HTMLInputElement>('input[type=file]'));
}
function pick(file: File) {
  fireEvent.change(input(), { target: { files: [file] } });
}
const sampleButton = () => screen.getByRole('button', { name: 'Try the sample project' });

beforeEach(() => {
  window.location.hash = '#/';
});
afterEach(cleanup);

describe('HomeScreen', () => {
  it('IN-1 renders the drop zone, "Choose a file" and "Try the sample project"', async () => {
    mockApi({ [LIST]: projectList });
    render(<HomeScreen />);
    expect(screen.getByRole('region', { name: 'Drop drawings or an archive' })).toBeTruthy();
    expect(screen.getByText('Choose a file')).toBeTruthy();
    expect(sampleButton()).toBeTruthy();
    await flush();
  });

  it('IN-2 the file input accepts zip, pdf, ifc, dxf, svg and image/*, one file only', async () => {
    mockApi({ [LIST]: projectList });
    render(<HomeScreen />);
    const accept = input().accept.split(',');
    for (const a of ['.zip', '.pdf', '.ifc', '.dxf', '.svg', 'image/*'])
      expect(accept).toContain(a);
    expect(input().multiple).toBe(false);
    await flush();
  });

  it('IN-3 picking a file sends one POST /api/projects?name=<encoded> with the File as body', async () => {
    const api = mockApi({ [LIST]: projectList, [UPLOAD]: projectStarted });
    render(<HomeScreen />);
    const file = new File(['PK'], 'my plän 1.zip');
    pick(file);
    await flush();
    const uploads = api.calls.filter((c) => c.method === 'POST');
    expect(uploads).toHaveLength(1);
    expect(uploads[0]?.url).toBe(`/api/projects?name=${encodeURIComponent('my plän 1.zip')}`);
    expect(uploads[0]?.body).toBe(file);
  });

  it('IN-7 while a request is in flight the box says so, controls are disabled, a second click sends nothing', async () => {
    const api = mockApi({ [LIST]: projectList, [SAMPLE]: never(), [UPLOAD]: never() });
    render(<HomeScreen />);
    fireEvent.click(sampleButton());
    fireEvent.click(sampleButton());
    await flush();
    expect(screen.getByText('Starting the sample…')).toBeTruthy();
    expect((sampleButton() as HTMLButtonElement).disabled).toBe(true);
    expect(input().disabled).toBe(true);
    expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    cleanup();

    mockApi({ [LIST]: projectList, [UPLOAD]: never() });
    render(<HomeScreen />);
    pick(new File(['x'], 'plan.pdf'));
    await flush();
    expect(screen.getByText('Uploading plan.pdf…')).toBeTruthy();
    expect((sampleButton() as HTMLButtonElement).disabled).toBe(true);
  });

  it('IN-8 on 202 the location becomes #/p/<id>', async () => {
    mockApi({ [LIST]: projectList, [UPLOAD]: projectStarted, [SAMPLE]: projectStarted });
    render(<HomeScreen />);
    pick(new File(['x'], 'plan.pdf'));
    await flush();
    expect(window.location.hash).toBe(`#/p/${projectStarted.id}`);
    window.location.hash = '#/';
    fireEvent.click(sampleButton());
    await flush();
    expect(window.location.hash).toBe(`#/p/${projectStarted.id}`);
  });

  it('IN-9 the sample button sends POST /api/projects/sample?fresh=true with no body', async () => {
    const api = mockApi({ [LIST]: projectList, [SAMPLE]: projectStarted });
    render(<HomeScreen />);
    fireEvent.click(sampleButton());
    await flush();
    const post = api.calls.find((c) => c.method === 'POST');
    expect(post?.url).toBe('/api/projects/sample?fresh=true');
    expect(post?.body).toBeUndefined();
  });

  it.each([
    [413, 'too-large'],
    [429, 'busy'],
    [422, 'validation'],
    [404, 'not-found'],
  ])('IN-10 a %i shows detail and code (%s) and re-enables the controls', async (status, code) => {
    mockApi({ [LIST]: projectList, [SAMPLE]: reply(status, { ...error, code }) });
    render(<HomeScreen />);
    fireEvent.click(sampleButton());
    await flush();
    expect(screen.getByText(error.detail, { exact: false })).toBeTruthy();
    expect(screen.getByText(code, { exact: false })).toBeTruthy();
    expect((sampleButton() as HTMLButtonElement).disabled).toBe(false);
    expect(input().disabled).toBe(false);
  });

  it('"Choose a file" is a focusable button that opens the hidden file input', async () => {
    mockApi({ [LIST]: projectList });
    render(<HomeScreen />);
    const button = screen.getByRole('button', { name: 'Choose a file' });
    button.focus();
    expect(document.activeElement).toBe(button);
    const click = vi.spyOn(input(), 'click');
    fireEvent.click(button);
    expect(click).toHaveBeenCalledTimes(1);
    expect(input().hidden).toBe(true);
    await flush();
  });

  function sized(size: number) {
    const file = new File(['x'], 'big.zip');
    Object.defineProperty(file, 'size', { value: size });
    return file;
  }
  const LIMIT = info.limits.upload_mb * 2 ** 20;
  const INFO = 'GET /api/info';

  it('IN-4 a file over limits.upload_mb is refused with uploadTooLarge and nothing is sent', async () => {
    const api = mockApi({ [INFO]: info, [LIST]: projectList, [UPLOAD]: projectStarted });
    render(
      <InfoProvider>
        <HomeScreen />
      </InfoProvider>,
    );
    await flush();
    pick(sized(LIMIT + 1));
    await flush();
    expect(screen.getByText(must(uploadTooLarge(LIMIT + 1, info.limits)))).toBeTruthy();
    expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(0);
    pick(sized(LIMIT));
    await flush();
    expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  });

  it.each([
    ['pending', never()],
    ['failed', reply(500, error)],
  ])('IN-5 with /api/info %s any size is uploaded', async (_, answer) => {
    const api = mockApi({ [INFO]: answer, [LIST]: projectList, [UPLOAD]: projectStarted });
    render(
      <InfoProvider>
        <HomeScreen />
      </InfoProvider>,
    );
    await flush();
    pick(sized(LIMIT * 10));
    await flush();
    expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  });

  it('IN-52 home: the hero, the five format chips and no edit-plan link', async () => {
    mockApi({});
    render(<HomeScreen />);
    expect(
      screen.getByRole('heading', { level: 1, name: 'Every answer, pointed at the drawing.' }),
    ).toBeTruthy();
    const chips = screen.getByRole('list', { name: 'Formats' });
    expect(
      within(chips)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      'IFC models',
      'DXF',
      'Vector PDF · SVG',
      'PNG · JPG scans and photos',
      'ZIP archives',
    ]);
    expect(screen.queryByText(/house plan/i)).toBeNull();
    await flush();
  });

  it('IN-53 a link "Earlier uploads are in Workspaces" to #/workspaces, and no GET /api/projects', async () => {
    const api = mockApi({});
    render(<HomeScreen />);
    await flush();
    expect(
      screen.getByRole('link', { name: 'Earlier uploads are in Workspaces' }).getAttribute('href'),
    ).toBe('#/workspaces');
    expect(api.calls.filter((c) => c.url === '/api/projects')).toHaveLength(0);
  });
});
