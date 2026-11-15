import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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
    expect(screen.getByText('Sent plan.pdf (1 KB): waiting for the server…')).toBeTruthy();
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

  it('IN-52 home: the hero, the six format chips (a scanned PDF named) and no edit-plan link', async () => {
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
      'PDF, drawn or scanned',
      'SVG',
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

// Bogdan 2026-11-15: the upload says it is sending (bytes, %), that the server received it, then moves on to the
// extraction; a failure says what failed, with a retry.
describe('upload: sending, received, failed', () => {
  /** An XHR whose upload this test drives: `progress`, `answer` (status + JSON body) or `drop` (network). */
  class HeldXhr {
    static last: HeldXhr | null = null;
    static sent = 0;
    status = 0;
    responseText = '';
    upload: { onprogress: ((e: Partial<ProgressEvent>) => void) | null } = { onprogress: null };
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onabort: (() => void) | null = null;
    open() {
      HeldXhr.last = this; // the test drives it
    }
    setRequestHeader() {
      return undefined;
    }
    abort() {
      return undefined;
    }
    send() {
      HeldXhr.sent++;
    }
    progress(loaded: number, total: number) {
      act(() => {
        this.upload.onprogress?.({ lengthComputable: true, loaded, total });
      });
    }
    answer(status: number, body: unknown) {
      this.status = status;
      this.responseText = JSON.stringify(body);
      this.onload?.();
    }
    drop() {
      this.onerror?.();
    }
  }
  const MB = 2 ** 20;
  function held(): HeldXhr {
    mockApi({ [LIST]: projectList });
    HeldXhr.last = null;
    HeldXhr.sent = 0;
    vi.stubGlobal('XMLHttpRequest', HeldXhr);
    render(<HomeScreen />);
    const file = new File(['x'], 'site.zip');
    Object.defineProperty(file, 'size', { value: 2 * MB });
    pick(file);
    const xhr = HeldXhr.last as HeldXhr | null;
    if (!xhr) throw new Error('no upload was sent');
    return xhr;
  }
  afterEach(() => {
    sessionStorage.clear();
  });

  it('while sending: the bytes sent of the total and the percent, as a progress bar', () => {
    const xhr = held();
    xhr.progress(MB / 2, 2 * MB);
    expect(screen.getByText('Sending site.zip: 0.5 of 2.0 MB (25%)')).toBeTruthy();
    expect(screen.getByRole('progressbar', { name: 'Upload' }).getAttribute('value')).toBe('25');
  });

  it('on 202: what the server received is kept for the extraction view, which opens without a click', async () => {
    const xhr = held();
    xhr.progress(2 * MB, 2 * MB);
    expect(screen.getByText('Sent site.zip (2.0 MB): waiting for the server…')).toBeTruthy();
    xhr.answer(202, projectStarted);
    await flush();
    expect(window.location.hash).toBe(`#/p/${projectStarted.id}`);
    expect(JSON.parse(must(sessionStorage.getItem(`uploaded:${projectStarted.id}`)))).toEqual({
      name: 'site.zip',
      bytes: 2 * MB,
    });
  });

  it('the connection lost while sending says so and where; Retry sends the file again', async () => {
    const xhr = held();
    xhr.progress(MB, 2 * MB);
    xhr.drop();
    await flush();
    expect(screen.getByRole('alert').textContent).toContain(
      'The connection was lost while sending site.zip (at 50%).',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(HeldXhr.sent).toBe(2);
  });

  it('a file the server refuses says the server refused it, with its detail; Retry is offered', async () => {
    const xhr = held();
    xhr.answer(413, { detail: 'the upload is over 200 MB', code: 'too-large' });
    await flush();
    expect(screen.getByRole('alert').textContent).toContain(
      'The server refused site.zip: the upload is over 200 MB',
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('a refusal whose detail starts with the file name says the name once', async () => {
    const xhr = held();
    xhr.answer(422, { detail: 'site.zip: the upload is empty', code: 'invalid' });
    await flush();
    expect(screen.getByRole('alert').textContent).toContain(
      'The server refused site.zip: the upload is empty',
    );
    expect(screen.getByRole('alert').textContent).not.toContain('site.zip: site.zip');
  });

  it('a new mistake replaces the last failed upload: no stale failure beside the new note', async () => {
    const xhr = held();
    xhr.answer(422, { detail: 'site.zip: the upload is empty', code: 'invalid' });
    await flush();
    fireEvent.drop(screen.getByRole('region', { name: 'Drop drawings or an archive' }), {
      dataTransfer: { files: [new File(['a'], 'a.pdf'), new File(['b'], 'b.pdf')] },
    });
    expect(screen.getByText('Drop one file or one zip at a time.')).toBeTruthy();
    expect(screen.queryByText(/The server refused/)).toBeNull();
  });
});
