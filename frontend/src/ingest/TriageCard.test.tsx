import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  drawing,
  error,
  fileReadAsPlan,
  relevanceRequest,
  triageRequest,
  triageStarted,
} from '../api/fixtures';
import type { FileStatus } from '../api';
import { mockApi, never, reply } from '../test/mockApi';
import { FileTraceScreen } from './FileTraceScreen';
import { flush, must, triageTrace, triaged, triagedVariants } from './testing';

const PID = triaged.id;
const NAME_KEY = 'countersign.surveyorName';
const file = (i: number) => must(triaged.files[i]);
const [south, site, street] = [file(1), file(2), file(3)];
const openSite = must(triagedVariants.open.files[2]);
const traceGet = (f: FileStatus) => `GET /api/projects/${PID}/files/${f.id}/trace`;
const POST = `POST /api/projects/${PID}/files/f3/relevance`;
const READ_DRAWING = `GET /api/drawings/${must(fileReadAsPlan.drawing_id)}`;

afterEach(cleanup);
beforeEach(() => {
  localStorage.clear();
});

async function show(file: FileStatus, routes: Record<string, unknown> = {}) {
  const api = mockApi({ [traceGet(file)]: triageTrace(file), ...routes });
  render(<FileTraceScreen projectId={PID} fileId={file.id} />);
  await flush();
  return api;
}

const card = () => within(screen.getByRole('region', { name: 'Is it a floor plan?' }));
const related = () => card().getByRole('button', { name: 'It is related' });
const unrelated = () => card().getByRole('button', { name: 'It is not related' });
const nameField = () => card().getByRole('textbox', { name: 'Your name' });

describe('TriageCard (file-triage.md)', () => {
  it('FT-6 shows class, chance, preview, description, relevance and judge', async () => {
    await show(south);
    const c = card();
    expect(
      c.getByRole('heading', { name: 'Not a floor plan: another kind of drawing' }),
    ).toBeTruthy();
    const text = must(screen.getByRole('region', { name: 'Is it a floor plan?' }).textContent);
    for (const s of [
      'Chance of a floor plan 3 % (fake classifier)',
      'A picture of the south elevation of a two-storey house.',
      'Subject: the south elevation of a two-storey house',
      'Described by fake describer',
      'Related to this project',
      "Related: Küche is on the project's plans.",
      'Matched on: Küche',
      'Judged by word judge',
    ])
      expect(text).toContain(s);
    const img = c.getByRole('img', { name: 'elevations/south.png as uploaded' });
    const preview = `/api/projects/${PID}/files/f2/preview.png`;
    // FT-6: the 400 rendition at 1x, 1600 only for dense screens (the API has no width between)
    expect(img.getAttribute('src')).toBe(`${preview}?width=400`);
    expect(img.getAttribute('srcset')).toBe(
      `${preview}?width=400 400w, ${preview}?width=1600 1600w`,
    );
    expect(img.getAttribute('sizes')).toBe('(max-width: 400px) 100vw, 400px');
    const seen = must(c.getByText('Text printed on it (2)').closest('details'));
    expect(seen.open).toBe(false);
    expect(seen.textContent).toContain('Küche');
    expect(seen.textContent).toContain('Süd');
  });

  it('FT-7 a failed preview says so', async () => {
    await show(south);
    fireEvent.error(card().getByRole('img', { name: 'elevations/south.png as uploaded' }));
    expect(card().getByText('Preview not available')).toBeTruthy();
  });

  it('FT-8 a file not described: the note once, no call buttons', async () => {
    await show(street);
    const text = must(screen.getByRole('region', { name: 'Is it a floor plan?' }).textContent);
    expect(text.split('not described: the model refused').length).toBe(2);
    expect(card().queryByRole('button', { name: /related/ })).toBeNull(); // no call: 422 no-description
  });

  it('FT-9 "It is related" sends the request fixture and shows the answer in place', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const api = await show(openSite, { [POST]: site });
    fireEvent.click(related());
    await flush();
    const post = must(api.calls.find((c) => c.method === 'POST'));
    expect(post.url).toBe(`/api/projects/${PID}/files/f3/relevance`);
    expect(post.body).toEqual(relevanceRequest);
    expect(
      card().getByText(
        'Related to this project: Ana’s call, 2026-11-14 08:05 UTC. The judge said: Not related.',
      ),
    ).toBeTruthy();
    expect(card().getByRole('button', { name: 'Undo the call' })).toBeTruthy();
    expect(api.calls.filter((c) => c.method === 'GET').length).toBe(1);
  });

  it('FT-10 both buttons are offered, even when the judge already said unrelated', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    const api = await show(openSite, { [POST]: site });
    fireEvent.click(unrelated());
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({
      verdict: 'unrelated',
      by: 'Ana',
    });
  });

  it('FT-11 the name: 100 characters, saved, trimmed, buttons disabled while empty', async () => {
    const api = await show(openSite, { [POST]: site });
    expect(nameField().getAttribute('maxlength')).toBe('100');
    expect((nameField() as HTMLInputElement).value).toBe('');
    expect((related() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(nameField(), { target: { value: '   ' } });
    expect((unrelated() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(nameField(), { target: { value: '  Ana ' } });
    fireEvent.click(related());
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(relevanceRequest);
    expect(localStorage.getItem(NAME_KEY)).toBe('Ana');
  });

  it('FT-11 a throwing localStorage leaves the field empty and the card working', async () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    await show(openSite);
    expect((nameField() as HTMLInputElement).value).toBe('');
    expect((related() as HTMLButtonElement).disabled).toBe(true);
    get.mockRestore();
  });

  it('FT-12 "Undo the call" sends {undo: true} and brings the form back', async () => {
    const api = await show(site, { [POST]: openSite });
    fireEvent.click(card().getByRole('button', { name: 'Undo the call' }));
    await flush();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({ undo: true });
    expect(related()).toBeTruthy();
  });

  it.each([
    [409, 'not-allowed', 'The project is still being read: a call can be made once it is done.'],
    [
      422,
      'no-description',
      'This file was not described, so there is nothing to judge or overrule.',
    ],
    [404, 'not-found', 'This file is no longer in the project. (boom, not-found)'],
    [500, 'internal', 'boom (internal)'],
  ])(
    'FT-13 %i %s is worded, the file stays, the buttons work again',
    async (status, code, line) => {
      localStorage.setItem(NAME_KEY, 'Ana');
      await show(openSite, { [POST]: reply(status, { ...error, code, detail: 'boom' }) });
      fireEvent.click(related());
      await flush();
      expect(card().getByRole('alert').textContent).toBe(line);
      expect((related() as HTMLButtonElement).disabled).toBe(false);
      expect(card().queryByRole('button', { name: 'Undo the call' })).toBeNull();
    },
  );

  it('FT-13 while the call is sent both buttons are disabled', async () => {
    localStorage.setItem(NAME_KEY, 'Ana');
    await show(openSite, { [POST]: never() });
    fireEvent.click(related());
    await flush();
    expect(card().getByText('Saving your call…')).toBeTruthy();
    expect((related() as HTMLButtonElement).disabled).toBe(true);
    expect((unrelated() as HTMLButtonElement).disabled).toBe(true);
  });

  it('FT-1 no card with triage off', async () => {
    await show(must(triaged.files[0]));
    expect(screen.queryByRole('region', { name: 'Is it a floor plan?' })).toBeNull();
  });

  describe('read it as a floor plan (FT-18, FT-19)', () => {
    const READ = `POST /api/projects/${PID}/files/f2/triage`;
    const readBtn = () => card().queryByRole('button', { name: 'Read it as a floor plan' });
    afterEach(() => {
      vi.restoreAllMocks();
      vi.useRealTimers();
    });

    it('FT-18 cancelled sends nothing; confirmed sends the request, polls, then offers the drawing', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
      localStorage.setItem(NAME_KEY, 'Ana');
      const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true);
      const answers = [triageTrace(south), triageTrace(triageStarted), triageTrace(fileReadAsPlan)];
      let n = 0;
      const api = mockApi({
        [traceGet(south)]: () => answers[Math.min(n++, answers.length - 1)],
        [READ]: reply(202, triageStarted),
        [READ_DRAWING]: drawing,
      });
      render(<FileTraceScreen projectId={PID} fileId="f2" />);
      await flush();
      fireEvent.click(must(readBtn()));
      expect(confirm).toHaveBeenCalledWith(
        "Read elevations/south.png as a floor plan? This can't be undone.",
      );
      expect(api.calls.some((c) => c.method === 'POST')).toBe(false);
      fireEvent.click(must(readBtn()));
      await flush();
      expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual(triageRequest);
      await act(() => vi.advanceTimersByTimeAsync(600));
      await flush();
      expect(screen.getByRole('link', { name: 'Open the drawing' }).getAttribute('href')).toBe(
        `#/p/${PID}/d/${must(fileReadAsPlan.drawing_id)}/engineer`,
      );
      expect(
        card().getByText('Ana had it read as a floor plan, 2026-11-14 08:05 UTC'),
      ).toBeTruthy();
      expect(readBtn()).toBeNull();
    });

    it('FT-18 needs a name, and is not offered for a plan, a call-less undescribed file is fine', async () => {
      await show(south);
      expect((must(readBtn()) as HTMLButtonElement).disabled).toBe(true);
      cleanup();
      await show(street);
      expect(readBtn()).toBeTruthy();
    });

    it('FT-19 a file read as a plan: the line, no button', async () => {
      await show(fileReadAsPlan, { [READ_DRAWING]: drawing });
      expect(
        card().getByRole('heading', { level: 2, name: 'Read as a floor plan on Ana’s call' }),
      ).toBeTruthy();
      expect(
        card().getByText('Triage said: another kind of drawing (3 % chance of a floor plan)'),
      ).toBeTruthy();
      expect(card().queryByRole('heading', { name: /^Not a floor plan/ })).toBeNull();
      expect(
        card().getByText('Ana had it read as a floor plan, 2026-11-14 08:05 UTC'),
      ).toBeTruthy();
      expect(readBtn()).toBeNull();
    });

    it.each([
      [
        409,
        'not-allowed',
        'The project is still being read, or this file is being read again already.',
      ],
      [
        422,
        'not-triaged',
        'Triage did not set this file aside, so there is nothing to read again.',
      ],
      [500, 'internal', 'boom (internal)'],
    ])('FT-19 %i %s is worded', async (status, code, line) => {
      localStorage.setItem(NAME_KEY, 'Ana');
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      await show(south, { [READ]: reply(status, { ...error, code, detail: 'boom' }) });
      fireEvent.click(must(readBtn()));
      await flush();
      expect(card().getByRole('alert').textContent).toBe(line);
      expect((must(readBtn()) as HTMLButtonElement).disabled).toBe(false);
    });
  });
});
