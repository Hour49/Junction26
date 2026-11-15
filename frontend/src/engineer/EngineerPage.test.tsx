import { cleanup as unmount, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import {
  drawingLabel,
  evidenceUrl,
  methodName,
  previewUrl,
  type AnswerView,
  type Row,
} from '../api';
import {
  answer,
  answerArea,
  answerConfidence,
  answerModel,
  answerRefused,
  answerResolved,
  drawing,
  error,
  info,
  project,
} from '../api/fixtures';
import { InfoProvider } from '../shell/info';
import { TIPS } from '../shell/tips';
import { mockApi, never } from '../test/mockApi';
import { EngineerPage } from './EngineerPage';
import { formatScore } from './format';
import {
  answerAgree,
  answerAreaExcluded,
  answerConflict,
  answerEdited,
  answerEstimate,
  answerNeedsPerson,
  answerSettled,
  answerSigned,
  answerHigh,
  answerLow,
  answerMedium,
  answerUnlocated,
  answerWithMarkup,
  drawingHello,
  drawingNoSuggestions,
  markup,
  projectNoFiles,
  projectOneDrawing,
  refusalWithMarkup,
} from './testing';

// EN-23: the score shows where the checks line names a second method (EN-93 hides it beside "one method").
const scoredAgree = {
  ...answerConfidence,
  quantity: answerConfidence.quantity && {
    ...answerConfidence.quantity,
    status: 'agree' as const,
    first: { method: 'plan_drawing', value: 2 },
    second: { method: 'ifc_model', value: 2 },
  },
};

/** A fresh page: unmounted, and no engineer thread kept in the tab (R3-L2). */
function cleanup() {
  unmount();
  sessionStorage.clear();
}

const PROJECT = '5e0c1a2b3d4f';
const DRAWING = drawing.id;
const DRAWING_ROUTE = `GET /api/drawings/${DRAWING}`;
// EN-87: the page names the drawing as the chat does (project.json's entry)
const NAME = 'Drawn plan 1';
const PROJECT_ROUTE = `GET /api/projects/${PROJECT}`;

/** Answers POST /api/ask with the given responses in order. */
function answers(...bodies: AnswerView[]) {
  const queue = [...bodies];
  return () => {
    const next = queue.shift();
    if (!next) throw new Error('no more answers queued');
    return next;
  };
}

function open(routes: Parameters<typeof mockApi>[0]) {
  // The project (position, arrows, original file) loads beside the drawing; a test may override it.
  const api = mockApi({ [PROJECT_ROUTE]: project, ...routes });
  render(<EngineerPage projectId={PROJECT} drawingId={DRAWING} />);
  return api;
}

const input = () => screen.getByRole<HTMLInputElement>('textbox', { name: 'Question' });
const askButton = () => screen.getByRole<HTMLButtonElement>('button', { name: 'Ask' });

async function typeAndAsk(question: string) {
  await screen.findByRole('textbox', { name: 'Question' });
  fireEvent.change(input(), { target: { value: question } });
  fireEvent.submit(input().closest('form') as HTMLFormElement);
}

async function askSuggestion(question: string) {
  fireEvent.click(await screen.findByRole('button', { name: question }));
}

const turn = (question: string) => screen.findByRole('article', { name: question });
const asks = (api: ReturnType<typeof mockApi>) => api.calls.filter((c) => c.method === 'POST');

const scrollMock = vi.fn();

beforeAll(() => {
  // jsdom has no layout, so no scrollIntoView.
  Element.prototype.scrollIntoView = scrollMock;
  // Radix (the shared Tip) measures with ResizeObserver, which jsdom lacks; set directly, since mockApi's
  // cleanup unstubs vi.stubGlobal after each test.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  cleanup();
});

describe('drawing header and ask box', () => {
  it('R1-PS-1 EN-49 the drawing is requested in the route project', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('heading', { name: NAME });
    const drawings = api.calls.filter((c) => c.url.startsWith('/api/drawings/'));
    expect(drawings.map((c) => c.url)).toEqual([`/api/drawings/${DRAWING}?project=${PROJECT}`]);
  });

  it('R1-PS-2 EN-50 every ask body carries the route project', async () => {
    const can = (answerRefused.refusal?.can_answer ?? []).map((s) => s.question);
    const failed = { status: 500, body: { detail: 'internal error', code: 'internal' } };
    let n = 0;
    const api = open({
      [DRAWING_ROUTE]: drawing,
      // 1 suggestion, 2 typed (refused), 3 can_answer (fails), 4 Try again.
      'POST /api/ask': (c: { body: unknown }) => {
        const { question } = c.body as { question: string };
        n += 1;
        if (n === 2) return answerRefused;
        if (n === 3) return failed;
        return { ...answer, question };
      },
    });
    const suggested = drawing.suggestions[0]?.question ?? '';
    await askSuggestion(suggested);
    await within(await turn(suggested)).findByTestId('answer-value');
    await typeAndAsk(answerRefused.question);
    const refused = await turn(answerRefused.question);
    const first = can[0] ?? '';
    fireEvent.click(await within(refused).findByRole('button', { name: first }));
    // The newest turn: the first can_answer question may also be the first suggestion.
    const t = (await screen.findAllByRole('article', { name: first })).at(-1) as HTMLElement;
    fireEvent.click(await within(t).findByRole('button', { name: 'Try again' }));
    await within(t).findByTestId('answer-value');
    const bodies = asks(api).map((c) => c.body);
    expect(bodies).toEqual(
      [suggested, answerRefused.question, first, first].map((question) => ({
        drawing_id: DRAWING,
        question,
        project_id: PROJECT,
      })),
    );
  });

  it('EN-1 opening the route requests the drawing once', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('heading', { name: NAME });
    const gets = api.calls.filter((c) => c.url.startsWith(`/api/drawings/${DRAWING}`));
    expect(gets).toHaveLength(1);
    expect(gets[0]?.method).toBe('GET');
  });

  it('EN-2 loading view while the drawing is pending, no ask box', () => {
    open({ [DRAWING_ROUTE]: () => never() });
    expect(screen.getByRole('status')).toBeTruthy();
    expect(screen.queryByRole('textbox', { name: 'Question' })).toBeNull();
  });

  it('EN-3 a 404 shows the error with detail, code and a link to the project', async () => {
    open({ [DRAWING_ROUTE]: { status: 404, body: error } });
    expect(await screen.findByText(/no drawing 0123456789abcdef/)).toBeTruthy();
    expect(screen.queryAllByText(/not-found/)).toHaveLength(0); // R2-C5: no raw code
    const back = screen.getByRole('link', { name: 'Back to the project' });
    expect(back.getAttribute('href')).toBe(`#/p/${PROJECT}`);
  });

  it('EN-4 the header shows the file and how it was read', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    expect(await screen.findByRole('heading', { name: NAME })).toBeTruthy();
    expect(
      screen.getByText(
        'drawn PDF route, read from plans/flat-a.pdf by PDF vector reader; second count where a question has one: PDF vector reader; questions: question templates',
      ),
    ).toBeTruthy();
  });

  it('QA #76 EN-4 a header without a second count says so', async () => {
    open({
      [DRAWING_ROUTE]: { ...drawing, reader: { ...drawing.reader, second_counter: 'none' } },
    });
    expect(
      await screen.findByText(
        'drawn PDF route, read from plans/flat-a.pdf by PDF vector reader; no second count; questions: question templates',
      ),
    ).toBeTruthy();
  });

  it('EN-6 one button per suggestion, in order', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('heading', { name: NAME });
    const row = screen.getByRole('group', { name: 'Suggested questions' });
    const names = within(row)
      .getAllByRole('button')
      .map((b) => b.textContent);
    expect(names).toEqual(drawing.suggestions.map((s) => s.question));
  });

  it('EN-8 before any question: page 1 without marks and the prompt', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    expect(await screen.findByText('Ask a question about this drawing.')).toBeTruthy();
    const img = screen.getByRole('img');
    expect(img.getAttribute('src')).toContain(`/api/drawings/${DRAWING}/pages/1.png`);
    expect(screen.queryByRole('button', { name: /^Mark / })).toBeNull();
  });

  it('EN-9 a suggestion click sends POST /api/ask with the drawing and question', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    await askSuggestion('How many doors are there?');
    await turn('How many doors are there?');
    expect(asks(api).map((c) => c.body)).toEqual([
      {
        drawing_id: 'adeefbbcc17559fc',
        question: 'How many doors are there?',
        project_id: PROJECT,
      },
    ]);
  });

  it('EN-10 the question is trimmed; an empty one sends nothing', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    await typeAndAsk('   ');
    expect(askButton().disabled).toBe(true);
    expect(asks(api)).toHaveLength(0);
    await typeAndAsk('  How many doors are there?  ');
    await turn('How many doors are there?');
    expect(asks(api).map((c) => c.body)).toEqual([
      { drawing_id: DRAWING, question: 'How many doors are there?', project_id: PROJECT },
    ]);
  });

  it('EN-12 while an ask is pending: the reading line, Ask disabled, no second request', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': () => never() });
    await typeAndAsk('How many doors are there?');
    const t = await turn('How many doors are there?');
    expect(within(t).getByText(`Reading ${NAME}…`)).toBeTruthy();
    await typeAndAsk('How many windows are there?');
    expect(askButton().disabled).toBe(true);
    expect(asks(api)).toHaveLength(1);
  });

  it('EN-46 the input is labelled "Question" and the button is "Ask"', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    expect(await screen.findByRole('textbox', { name: 'Question' })).toBeTruthy();
    expect(askButton()).toBeTruthy();
  });
});

describe('answers', () => {
  async function shown(a: AnswerView) {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(a) });
    await typeAndAsk(a.question);
    const t = await turn(a.question);
    await within(t).findByTestId('answer-value');
    return t;
  }

  it('EN-13 a count shows its value with no unit and the label', async () => {
    const t = await shown(answer);
    expect(within(t).getByTestId('answer-value').textContent).toBe('2');
    // Vellum: the sentence, composed from the answer, the noun and the label (#14 c6874945888).
    expect(t.querySelector('.en-sentence')?.textContent).toBe(
      'There are 2 doors. Every element, room and plan the drawing lists counts once.',
    );
  });

  it('EN-14 a sum shows 52.27 m²', async () => {
    const t = await shown(answerArea);
    expect(within(t).getByTestId('answer-value').textContent).toBe('52.27 m²');
  });

  it('EN-15 the viewer draws the two numbered marks on page 1', async () => {
    const t = await shown(answer);
    expect(within(t).getByRole('button', { name: /^Mark 1: door/ })).toBeTruthy();
    expect(within(t).getByRole('button', { name: /^Mark 2: door/ })).toBeTruthy();
    expect(within(t).getByRole('img').getAttribute('src')).toContain('/pages/1.png');
  });

  it('EN-16 the mark list: one row per mark, with the value for a sum', async () => {
    const t = await shown(answer);
    const rows = within(t)
      .getAllByRole('listitem')
      .map((li) => li.textContent);
    expect(rows).toContain('1 door');
    expect(rows).toContain('2 door');
    cleanup();
    const s = await shown(answerArea);
    const sumRows = within(s)
      .getAllByRole('listitem')
      .map((li) => li.textContent);
    expect(sumRows).toContain('1 Küche 22.40 m²');
  });

  it('EN-91 the mark list shows 12 rows and "Show all <n>", which toggles to every row', async () => {
    const m0 = (answer.marks[0] ?? {}) as (typeof answer.marks)[number];
    const many = {
      ...answer,
      marks: Array.from({ length: 38 }, (_, i) => ({ ...m0, id: `e${String(i + 1)}`, n: i + 1 })),
    };
    const t = await shown(many);
    const list = () => t.querySelectorAll('.en-marks li');
    expect(list()).toHaveLength(12);
    const more = within(t).getByRole('button', { name: 'Show all 38' });
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(list()).toHaveLength(38);
    const fewer = within(t).getByRole('button', { name: 'Show fewer' });
    expect(fewer.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(fewer);
    expect(list()).toHaveLength(12);
    cleanup();
    const two = await shown(answer);
    expect(two.querySelectorAll('.en-marks li')).toHaveLength(2);
    expect(within(two).queryByRole('button', { name: /^Show all/ })).toBeNull();
  });

  it('EN-18 the counting rule', async () => {
    const t = await shown(answer);
    expect(
      within(t).getByText(
        'Counting rule: every element, room and plan the drawing lists counts once',
      ),
    ).toBeTruthy();
  });

  it("QA R3-A2 EN-93 one method, no second check: no second reader's score beside it", async () => {
    expect(answerConfidence.confidence).not.toBeNull();
    const t = await shown(answerConfidence);
    expect(within(t).getByText('Measured by one method; no second check.')).toBeTruthy();
    expect(within(t).queryByText(/Second reader's score/)).toBeNull();
    const details = within(t).getByText('Details').closest('details') as HTMLElement;
    expect(within(details).getByText('Signal: g1main')).toBeTruthy();
  });

  it('EN-20 the viewer gets the proof legend: one colour per room label', async () => {
    const t = await shown(answerArea);
    const html = t.innerHTML;
    expect(html).toContain('#d62728');
    expect(html).toContain('#1f77b4');
  });

  it("QA R1 EN-23 the second reader's score, no signal name on the card, never a probability", async () => {
    const conf = scoredAgree.confidence;
    expect(conf).not.toBeNull();
    const signal = conf?.signal ?? '';
    const t = await shown(scoredAgree);
    expect(
      within(t).getByText(
        `Second reader's score ${formatScore(conf?.score ?? NaN)} (not a probability)`,
      ),
    ).toBeTruthy();
    const details = within(t).getByText('Details').closest('details') as HTMLElement;
    expect(within(details).getByText(`Signal: ${signal}`)).toBeTruthy();
    const outside = t.textContent.replace(details.textContent, '');
    expect(outside).not.toContain(signal);
    expect(outside).not.toMatch(/confidence/i);
    expect(t.querySelector('.en-side')?.textContent).not.toContain('%');
    expect(outside.replace('not a probability', '')).not.toMatch(/probability/i);
    cleanup();
    const plain = await shown(answer);
    expect(within(plain).queryByText(/Second reader's score/)).toBeNull();
    expect(within(plain).queryByText(/^Signal:/)).toBeNull();
  });

  it('EN-24 the footer shows cost and time', async () => {
    const t = await shown(answer);
    expect(within(t).getByText('Cost $0')).toBeTruthy();
    expect(within(t).getByText('Time 2.0 ms')).toBeTruthy();
  });

  it('EN-31 the status shows in words', async () => {
    const t = await shown(answer);
    expect(within(t).getByText('One method')).toBeTruthy();
    cleanup();
    const c = await shown(answerConflict);
    expect(within(c).getByText('Methods disagree')).toBeTruthy();
  });

  it('R3 EN-33 a conflict shows both values with plain method names and the kept one', async () => {
    const t = await shown(answerConflict);
    expect(within(t).getByText(`22.40 m² by ${methodName('polygon_x_scale')}`)).toBeTruthy();
    expect(within(t).getByText(`30.00 m² by ${methodName('printed_label')}`)).toBeTruthy();
    // The checks panel is this screen's; the viewer's conflict legend is fe-viewer's.
    const checks = t.querySelector('.en-checks')?.textContent ?? '';
    expect(checks).not.toMatch(/polygon_x_scale|printed_label/);
    expect(
      within(t).getByText("Kept 30.00 m²: the printed label over the outline at the sheet's scale"),
    ).toBeTruthy();
  });

  it('EN-48 the big value has data-testid answer-value; a refusal has none', async () => {
    const t = await shown(answerArea);
    expect(within(t).getByTestId('answer-value').textContent).toBe('52.27 m²');
    cleanup();
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answerRefused) });
    await typeAndAsk(answerRefused.question);
    const r = await turn(answerRefused.question);
    await within(r).findByText("I can't answer that from this drawing.");
    expect(within(r).queryByTestId('answer-value')).toBeNull();
  });
});

describe('refusals and errors', () => {
  it('R3-final EN-39 a refusal: the sentence and the reason; no code, number, marks or links', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answerRefused) });
    await typeAndAsk('What colour is the roof?');
    const t = await turn('What colour is the roof?');
    expect(await within(t).findByText("I can't answer that from this drawing.")).toBeTruthy();
    expect(within(t).getByText(/This question isn't one I can turn into a count/)).toBeTruthy();
    expect(t.textContent).not.toContain('code:');
    expect(t.textContent).not.toContain(answerRefused.refusal?.code ?? 'unsupported-question');
    expect(within(t).queryByTestId('answer-value')).toBeNull();
    expect(within(t).queryByRole('button', { name: /^Mark / })).toBeNull();
    // The answer's own links (surveyor, picture) are absent; the drawing arrows stay (preqa-b, EN-56).
    expect(
      within(t)
        .queryAllByRole('link')
        .filter((l) => !l.closest('nav')),
    ).toEqual([]);
  });

  it('EN-40 a can_answer button asks that question', async () => {
    const can = (answerRefused.refusal?.can_answer ?? []).map((s) => s.question);
    const first = can[0] ?? '';
    const api = open({
      [DRAWING_ROUTE]: drawing,
      // The refusal for its own question; answer.json echoing any other question.
      'POST /api/ask': (c: { body: unknown }) => {
        const { question } = c.body as { question: string };
        return question === answerRefused.question ? answerRefused : { ...answer, question };
      },
    });
    await typeAndAsk(answerRefused.question);
    const t = await turn(answerRefused.question);
    const buttons = await within(t).findAllByRole('button');
    expect(can.length).toBeGreaterThan(0);
    expect(buttons.map((b) => b.textContent)).toEqual(can);
    fireEvent.click(within(t).getByRole('button', { name: first }));
    await within(await turn(first)).findByTestId('answer-value');
    expect(asks(api).map((c) => (c.body as { question: string }).question)).toEqual([
      answerRefused.question,
      first,
    ]);
  });

  it('EN-41 a failed ask shows detail and code; Try again resends; Ask is enabled', async () => {
    const failed = { status: 422, body: { detail: 'question too long', code: 'validation' } };
    let calls = 0;
    const api = open({
      [DRAWING_ROUTE]: drawing,
      'POST /api/ask': () => (++calls === 1 ? failed : answer),
    });
    await typeAndAsk('How many doors are there?');
    const t = await turn('How many doors are there?');
    expect(
      await within(t).findByText('The question could not be answered: question too long'),
    ).toBeTruthy();
    expect(within(t).queryByText(/validation/)).toBeNull(); // R3-L7: no raw 'code: …' line
    fireEvent.change(input(), { target: { value: 'x' } });
    expect(askButton().disabled).toBe(false);
    fireEvent.click(within(t).getByRole('button', { name: 'Try again' }));
    await within(t).findByTestId('answer-value');
    expect(asks(api).map((c) => (c.body as { question: string }).question)).toEqual([
      'How many doors are there?',
      'How many doors are there?',
    ]);
  });

  it('EN-42 strings from the server render as text', async () => {
    const a = answerWithMarkup();
    open({
      [DRAWING_ROUTE]: drawing,
      'POST /api/ask': answers(a, refusalWithMarkup(answerRefused)),
    });
    await typeAndAsk('How many doors are there?');
    const t = await turn(markup);
    await within(t).findByTestId('answer-value');
    expect(within(t).getAllByText(markup).length).toBeGreaterThan(1);
    await typeAndAsk('What colour is the roof?');
    const r = await turn('What colour is the roof?');
    expect(await within(r).findByText(new RegExp(markup.replace(/[()]/g, '\\$&')))).toBeTruthy();
    expect(document.querySelector('img[src="x"]')).toBeNull();
  });
});

describe('thread', () => {
  it('EN-43 a second answer comes after the first; the counter reads 2 asked', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer, answerArea) });
    await typeAndAsk(answer.question);
    await within(await turn(answer.question)).findByTestId('answer-value');
    await typeAndAsk(answerArea.question);
    await within(await turn(answerArea.question)).findByTestId('answer-value');
    const articles = screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'));
    expect(articles).toEqual([answer.question, answerArea.question]);
    expect(screen.getByText('2 asked')).toBeTruthy();
  });

  it('R3-L2 the answered turns come back after a reload of the tab; the counter goes on', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer, answerArea) });
    await typeAndAsk(answer.question);
    await within(await turn(answer.question)).findByTestId('answer-value');
    unmount(); // the reload: the page mounts again in the same tab, its storage kept
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answerArea) });
    expect(await within(await turn(answer.question)).findByTestId('answer-value')).toBeTruthy();
    expect(screen.getByText('1 asked')).toBeTruthy();
    await typeAndAsk(answerArea.question);
    await within(await turn(answerArea.question)).findByTestId('answer-value');
    const articles = screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'));
    expect(articles).toEqual([answer.question, answerArea.question]);
  });

  it('R3-L2 a thread kept for another drawing or a bad stored value starts empty', async () => {
    sessionStorage.setItem(`engineer-thread:${PROJECT}:other`, JSON.stringify([{ id: 1 }]));
    sessionStorage.setItem(`engineer-thread:${PROJECT}:${DRAWING}`, '{not json');
    open({ [DRAWING_ROUTE]: drawing });
    expect(await screen.findByText('Ask a question about this drawing.')).toBeTruthy();
    expect(screen.getByText('0 asked')).toBeTruthy();
  });

  it('EN-47 each turn is an article named by its question', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    await askSuggestion('How many doors are there?');
    const t = await turn('How many doors are there?');
    expect(t.tagName).toBe('ARTICLE');
    expect(await within(t).findByTestId('answer-value')).toBeTruthy();
  });

  it('review fix 1: when the answer arrives, the new turn is scrolled into view', async () => {
    const scroll = scrollMock;
    let arrive: (a: AnswerView) => void = () => undefined;
    const held = new Promise<AnswerView>((resolve) => {
      arrive = resolve;
    });
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': () => held });
    await typeAndAsk(answerArea.question);
    const t = await turn(answerArea.question);
    await within(t).findByText(`Reading ${NAME}…`);
    const before = scroll.mock.calls.length;
    arrive(answerArea);
    await within(t).findByTestId('answer-value');
    expect(scroll.mock.calls.length).toBeGreaterThan(before);
    expect(scroll.mock.contexts.at(-1)).toBe(t);
  });

  it('R2 qa-3 EN-52 the footer Details keeps the disclosure marker', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    await askSuggestion(answer.question);
    const t = await turn(answer.question);
    await within(t).findByTestId('answer-value');
    const details = within(t).getByText('Details');
    expect(details.tagName).toBe('SUMMARY');
    expect(details.style.display).toBe('list-item');
  });

  it('EN-60 suggestion chips sit after the thread; after a refusal they show once, in the refusal card', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answerRefused, answer) });
    const before = await screen.findByRole('group', { name: 'Suggested questions' });
    expect(before.closest('article')).toBeNull();
    await typeAndAsk(answerRefused.question);
    const t = await turn(answerRefused.question);
    await within(t).findByText("I can't answer that from this drawing.");
    // orch 12:20 (testers): no second row of the same questions right under the refusal
    for (const q of answerRefused.refusal?.can_answer ?? []) {
      expect(screen.getAllByRole('button', { name: q.question })).toHaveLength(1);
      expect(within(t).getByRole('button', { name: q.question })).toBeTruthy();
    }
    expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull();
    // the next answer brings the row back after the thread
    fireEvent.click(within(t).getByRole('button', { name: answer.question }));
    await within(await turn(answer.question)).findByTestId('answer-value');
    const row = screen.getByRole('group', { name: 'Suggested questions' });
    expect(row.closest('article')).toBeNull();
    expect(screen.queryByText('Suggested questions')).toBeNull();
    expect(document.querySelector('details:not(.en-details)')).toBeNull();
  });
});

describe('EN-92 a thread of refusals keeps the drawing in view', () => {
  it('shows the page after a refusal, and only the answer card once a question is answered', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answerRefused, answer) });
    const empty = () => screen.queryByRole('figure', { name: 'Drawing' });
    expect(await screen.findByRole('figure', { name: 'Drawing' })).toBeTruthy();
    await typeAndAsk(answerRefused.question);
    const t = await turn(answerRefused.question);
    await within(t).findByText("I can't answer that from this drawing.");
    // QA r2 R2-A2: a judge whose first question is refused still sees the sheet
    expect(empty()).toBeTruthy();
    fireEvent.click(within(t).getByRole('button', { name: answer.question }));
    await within(await turn(answer.question)).findByTestId('answer-value');
    expect(document.querySelector('.en-card--empty')).toBeNull();
  });
});

/** Asks one question and waits for its answer, refusal or error to show. */
async function shownTurn(a: AnswerView, d = drawing) {
  open({ [DRAWING_ROUTE]: d, 'POST /api/ask': answers(a) });
  await typeAndAsk(a.question);
  const t = await turn(a.question);
  await within(t).findByText(/^(Cost |I can't answer)/);
  return t;
}

const rowTexts = (t: HTMLElement) =>
  within(t)
    .getAllByRole('listitem')
    .map((li) => li.textContent);

describe('extended answers', () => {
  it('EN-28 a building-model answer: no viewer, objects, storeys and the arithmetic', async () => {
    const t = await shownTurn(answerModel);
    expect(within(t).queryByRole('img')).toBeNull();
    const objects = within(t).getByRole('table', { name: 'Model objects' });
    expect(within(objects).getByText('Door 1')).toBeTruthy();
    expect(within(objects).getAllByText('Ground floor').length).toBeGreaterThan(0);
    expect(within(objects).getByText('000000000000000000000K')).toBeTruthy();
    const storeys = within(t).getByRole('table', { name: 'Objects per storey' });
    const row = within(storeys).getByRole('row', { name: /Ground floor/ });
    const head = within(storeys)
      .getAllByRole('columnheader')
      .map((h) => h.textContent);
    const cells = within(row)
      .getAllByRole('cell')
      .map((c) => c.textContent);
    expect(cells[head.indexOf('door') - 1]).toBe('2');
    expect(cells[head.indexOf('window') - 1]).toBe('3');
    expect(within(t).getByText('2 door objects in the model on Ground floor')).toBeTruthy();
  });

  it('EN-30 Send to surveyor links to the surveyor view on the key; absent on a refusal', async () => {
    const t = await shownTurn(answer);
    const link = within(t).getByRole('link', { name: 'Send to surveyor' });
    expect(link.getAttribute('href')).toBe(`#/p/${PROJECT}/d/${DRAWING}/surveyor?q=door`);
    cleanup();
    const c = await shownTurn(answerConflict);
    expect(within(c).getByRole('link', { name: 'Send to surveyor' }).getAttribute('href')).toBe(
      `#/p/${PROJECT}/d/${DRAWING}/surveyor?q=area%3Aroom%7Cname%3D1.01`,
    );
    cleanup();
    const r = await shownTurn(answerRefused);
    expect(within(r).queryByRole('link', { name: 'Send to surveyor' })).toBeNull();
  });

  it('#90 EN-29 the picture link carries the project; only when confidence is null', async () => {
    const t = await shownTurn(answer);
    const link = within(t).getByRole('link', { name: 'Picture of this answer' });
    expect(link.getAttribute('href')).toBe(
      `/api/drawings/adeefbbcc17559fc/evidence.png?question=How%20many%20doors%20are%20there%3F&width=1600&project=${PROJECT}`,
    );
    expect(link.getAttribute('target')).toBe('_blank');
    cleanup();
    const s = await shownTurn(answerConfidence);
    expect(within(s).queryByRole('link', { name: 'Picture of this answer' })).toBeNull();
  });

  it('QA #76 EN-26 where this came from: no second count, or the counter by name', async () => {
    expect(answer.reader.second_counter).toBe('none');
    const t = await shownTurn(answer);
    expect(
      within(t).getByText(
        'PDF vector reader read plans/flat-a.pdf (drawn PDF route), no second count',
      ),
    ).toBeTruthy();
    cleanup();
    const counted = await shownTurn({
      ...answer,
      reader: { ...answer.reader, second_counter: 'ifc' },
    });
    expect(
      within(counted).getByText(
        'PDF vector reader read plans/flat-a.pdf (drawn PDF route), second count by IFC model',
      ),
    ).toBeTruthy();
  });

  it('EN-27 details are collapsed, with the query and method; no How line when null', async () => {
    const t = await shownTurn(answer);
    const details = within(t).getByText('Details').closest('details');
    expect(details?.open).toBe(false);
    const inside = within(details as HTMLElement);
    expect(inside.getByText('Query: door count')).toBeTruthy();
    expect(inside.getByText('Method: takeoff')).toBeTruthy();
    expect(inside.queryByText(/^How:/)).toBeNull();
  });

  it('EN-27 printed-names: Query shows the printed label, not the internal key', async () => {
    const area = within(await shownTurn(answerArea))
      .getByText('Details')
      .closest('details');
    const label = answerArea.quantity?.label ?? '';
    expect(within(area as HTMLElement).getByText(`Query: ${label}`)).toBeTruthy();
    expect(within(area as HTMLElement).queryByText(/^Query: area:room/)).toBeNull();
  });

  it('EN-27 printed-names: Query falls back to the key when the label is empty', async () => {
    if (!answer.quantity) throw new Error('answer.json has a quantity');
    const bare = await shownTurn({ ...answer, quantity: { ...answer.quantity, label: '' } });
    const details = within(bare).getByText('Details').closest('details');
    expect(within(details as HTMLElement).getByText('Query: door')).toBeTruthy();
  });

  it('QA R1 EN-27 the Details summary sits in the footer row, aligned on the baseline', async () => {
    const t = await shownTurn(answer);
    const footer = t.querySelector('footer') as HTMLElement;
    const details = within(footer).getByText('Details').closest('details') as HTMLElement;
    expect(details.parentElement).toBe(footer);
    expect(footer.style.alignItems).toBe('baseline');
  });

  it('QA R1 EN-28 model tables never break inside a word and scroll sideways', async () => {
    const t = await shownTurn(answerModel);
    for (const name of ['Model objects', 'Objects per storey']) {
      const table = within(t).getByRole('table', { name });
      expect(table.style.overflowWrap).toBe('normal');
      expect(table.style.wordBreak).toBe('normal');
      expect(table.parentElement?.style.overflowX).toBe('auto');
    }
  });

  it('R2 #80 EN-51 the read-as note leads the How line, in full', async () => {
    const note = "read 'mnay' as 'many'";
    const own = 'the scale is estimated from a door width';
    const misspelt = { ...answer, question: 'How mnay doors are there?' };
    const cases: [string, string][] = [
      [`${note}; ${own}`, `How: ${note}; ${own}`],
      [note, `How: ${note}`],
    ];
    for (const [explanation, line] of cases) {
      const t = await shownTurn({ ...misspelt, explanation });
      const details = within(t).getByText('Details').closest('details') as HTMLElement;
      expect(within(details).getByText(line).tagName).toBe('P');
      cleanup();
    }
  });

  it('R2-2-1 EN-51 the read-as note is on the card, Details closed; answers and refusals', async () => {
    const note = "read 'mnay' as 'many'";
    const shownNote = "Read 'mnay' as 'many'";
    const cases: AnswerView[] = [
      { ...answer, explanation: `${note}; the scale is estimated from a door width` },
      { ...answer, explanation: note },
      { ...answerRefused, explanation: `${note}; ${answerRefused.explanation ?? ''}` },
    ];
    for (const a of cases) {
      const t = await shownTurn({ ...a, question: 'How mnay doors are there?' });
      const shown = within(t).getByText(shownNote);
      expect(shown.closest('details')).toBeNull();
      const details = t.querySelector('details');
      if (details) expect(details.open).toBe(false);
      const value = within(t).queryByTestId('answer-value');
      if (value) {
        expect(
          shown.compareDocumentPosition(value) & Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
      }
      cleanup();
    }
    for (const a of [answer, answerRefused]) {
      expect(a.explanation === null || !a.explanation.startsWith("read '")).toBe(true);
      const t = await shownTurn(a);
      expect(within(t).queryByText(/^Read '/)).toBeNull();
      cleanup();
    }
  });

  it('EN-19 the arithmetic line for a sum; none when null', async () => {
    const t = await shownTurn(answerArea);
    expect(
      within(t).getByText(
        '22.4 + 2.49 + 12.45 + 14.93 = 52.27 m²; left out: Balkon 12.45 (outdoor room)',
      ),
    ).toBeTruthy();
    cleanup();
    const c = await shownTurn(answer);
    expect(c.querySelector('.en-arith')).toBeNull();
  });

  it('EN-21 an excluded mark: sign – and the reason, no number', async () => {
    const t = await shownTurn(answerAreaExcluded);
    expect(rowTexts(t)).toContain('– Balkon left out by the rule: outdoor room');
  });

  it('EN-20 a legend note shows as text', async () => {
    const t = await shownTurn(answerUnlocated);
    expect(within(t).getByText(/1 counted without a mark \(second reader\)/)).toBeTruthy();
  });

  it('EN-32 a signed answer shows who verified it and when', async () => {
    const t = await shownTurn(answerSigned);
    expect(within(t).getByText('Verified by Ana, 2026-11-14 01:40 UTC')).toBeTruthy();
    expect(within(t).getByText('Verified')).toBeTruthy();
  });

  it('EN-34 nobody decided: the surveyor sentence, no Kept line', async () => {
    const t = await shownTurn(answerNeedsPerson);
    expect(
      within(t).getByText(
        'No rule decides. A surveyor has to settle it before this value can be used.',
      ),
    ).toBeTruthy();
    expect(within(t).queryByText(/^Kept /)).toBeNull();
  });

  it('EN-35 agree shows the second method; single says one method', async () => {
    const t = await shownTurn(answerAgree);
    expect(
      within(t).getByText(`Second method (${methodName('ifc_model')}): 2, agrees`),
    ).toBeTruthy();
    expect(t.querySelector('.en-checks')?.textContent).not.toContain('ifc_model');
    cleanup();
    const s = await shownTurn(answer);
    expect(within(s).getByText('Measured by one method; no second check.')).toBeTruthy();
  });

  it('R3-final EN-36 an estimate shows its reason and says it was estimated once', async () => {
    const t = await shownTurn(answerEstimate);
    expect(within(t).getByText('Estimate: scale estimated from a door width')).toBeTruthy();
    expect(within(t).getByText('Estimated by one method; no second check.')).toBeTruthy();
    expect(within(t).queryByText('Measured by one method; no second check.')).toBeNull();
  });

  it('EN-37 an edited answer: was 2, the rejected and added rows', async () => {
    const t = await shownTurn(answerEdited);
    expect(within(t).getByText('Changed in review, was 2')).toBeTruthy();
    expect(rowTexts(t)).toContain('× door rejected by a surveyor');
    expect(rowTexts(t)).toContain('+3 item added by a surveyor');
  });

  it('EN-38 a settled value shows when and what', async () => {
    const t = await shownTurn(answerSettled);
    expect(
      within(t).getByText('Settled by a surveyor at 2026-11-14 01:30 UTC: 22.40 m²'),
    ).toBeTruthy();
  });

  it('EN-38 a settled value replaces the Kept line', async () => {
    const t = await shownTurn(answerSettled);
    expect(within(t).getByText(`30.00 m² by ${methodName('printed_label')}`)).toBeTruthy();
    expect(within(t).queryByText(/^Kept /)).toBeNull();
  });

  it('EN-22 the viewer draws the conflict tags A and B; none without a conflict', async () => {
    const t = await shownTurn(answerConflict);
    expect([...t.querySelectorAll('.vw-tag')].map((e) => e.textContent)).toEqual(['A', 'B']);
    cleanup();
    const s = await shownTurn(answer);
    expect(s.querySelectorAll('.vw-tag')).toHaveLength(0);
  });

  it('EN-17 a hovered row highlights its mark; a selected mark selects its row', async () => {
    const t = await shownTurn(answer);
    const row2 = within(t)
      .getAllByRole('listitem')
      .find((li) => li.textContent === '2 door') as HTMLElement;
    fireEvent.mouseEnter(row2);
    const badge2 = within(t).getByRole('button', { name: /^Mark 2: door/ });
    expect(badge2.className).toContain('vw-hot');
    fireEvent.mouseLeave(row2);
    expect(badge2.className).not.toContain('vw-hot');
    fireEvent.click(badge2);
    expect(row2.getAttribute('aria-selected')).toBe('true');
  });
});

describe('drawing header states', () => {
  it('EN-5 a hello reader: not read, never "by hello"', async () => {
    open({ [DRAWING_ROUTE]: drawingHello });
    await screen.findByText('No ready questions for this drawing.');
    const page = document.body.textContent;
    expect(page).toContain('not read (this setup has no reader for this kind of sheet)');
    expect(page).not.toContain('yet');
    expect(page).not.toContain('by hello');
    expect(
      screen.getByText(
        "This setup has no reader for this kind of sheet, so nothing on it was counted or measured. You can still ask about the project's other drawings.",
      ),
    ).toBeTruthy();
  });

  it('EN-7 no suggestions: the sentence and the ask box', async () => {
    open({ [DRAWING_ROUTE]: drawingNoSuggestions });
    expect(await screen.findByText('No ready questions for this drawing.')).toBeTruthy();
    expect(screen.getByRole('textbox', { name: 'Question' })).toBeTruthy();
  });

  it('EN-11 the question length limit from /api/info', async () => {
    mockApi({ 'GET /api/info': info, [DRAWING_ROUTE]: drawing, [PROJECT_ROUTE]: project });
    render(
      <InfoProvider>
        <EngineerPage projectId={PROJECT} drawingId={DRAWING} />
      </InfoProvider>,
    );
    await screen.findByRole('textbox', { name: 'Question' });
    fireEvent.change(input(), { target: { value: 'x'.repeat(2000) } });
    await screen.findByRole('button', { name: 'Ask' });
    expect(askButton().disabled).toBe(false);
    fireEvent.change(input(), { target: { value: 'x'.repeat(2001) } });
    expect(await screen.findByText('Questions are at most 2000 characters.')).toBeTruthy();
    expect(askButton().disabled).toBe(true);
  });
});

describe('Vellum (screen 4)', () => {
  it('EN-54 the turn: bubble, sentence with the rule, then the card: plan left, value, checks, rule, references right', async () => {
    const t = await shownTurn(answer);
    const parts = [...t.children].map((e) => e.className);
    expect(parts).toEqual(['en-bubble', 'en-sentence', 'v-card en-card']);
    expect(within(t).getByRole('figure', { name: 'Drawing' }).closest('.en-left')).toBeTruthy();
    // EN-86: the value sits in .en-head (its own grid area), the rest in .en-side
    const head = t.querySelector('.en-head') as HTMLElement;
    expect(within(head).getByTestId('answer-value').textContent).toBe('2');
    const side = t.querySelector('.en-side') as HTMLElement;
    const order = ['Checks', 'One method', 'Counting rule:', 'References'].map((x) =>
      side.textContent.indexOf(x),
    );
    expect(order.every((at, i) => at >= 0 && (i === 0 || at > (order[i - 1] ?? 0)))).toBe(true);
    for (const word of ['Confidence', 'High', 'Medium', 'Low', 'Finland', 'Switzerland']) {
      expect(t.textContent).not.toContain(word);
    }
  });

  it('EN-55 page meta: kind and route on the viewer, Also as links, the position', async () => {
    const t = await shownTurn(answer);
    const fig = within(t).getByRole('figure', { name: 'Drawing' });
    expect(fig.textContent).toContain('PDF vector · drawn PDF route');
    const also = within(t).getByRole('link', { name: 'flat-a.png' });
    expect(also.getAttribute('href')).toBe(`#/p/${PROJECT}/d/c9b719f715357201/engineer`);
    expect(within(t).getByText('1 / 6').getAttribute('aria-live')).toBe('polite');
  });

  it('EN-56 previous and next drawing wrap round; none for one drawing or before the project', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    const next = await screen.findByRole('link', { name: 'Next drawing' });
    expect(next.getAttribute('href')).toBe(
      `#/p/${PROJECT}/d/${project.drawings[1]?.drawing_id ?? ''}/engineer`,
    );
    expect(screen.getByRole('link', { name: 'Previous drawing' }).getAttribute('href')).toBe(
      `#/p/${PROJECT}/d/1db9bcf1e67e27a3/engineer`,
    );
  });

  it('PREQA-B EN-56 a drawing with no page (building model) has the arrows and position', async () => {
    open({ [DRAWING_ROUTE]: { ...drawing, pages: [] } });
    const nav = await screen.findByRole('navigation', { name: 'Drawings' });
    expect(within(nav).getByRole('link', { name: 'Next drawing' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Previous drawing' })).toBeTruthy();
    expect(within(nav).getByText('1 / 6').getAttribute('aria-live')).toBe('polite');
  });

  it.each([
    ['a building-model answer', answerModel],
    ['a refusal', answerRefused],
  ])('PREQA-B EN-56 %s card has the arrows and position', async (_, a) => {
    const t = await shownTurn(a);
    const nav = await within(t).findByRole('navigation', { name: 'Drawings' });
    expect(within(nav).getByRole('link', { name: 'Next drawing' }).getAttribute('href')).toBe(
      `#/p/${PROJECT}/d/${project.drawings[1]?.drawing_id ?? ''}/engineer`,
    );
    expect(within(nav).getByRole('link', { name: 'Previous drawing' })).toBeTruthy();
    expect(within(nav).getByText('1 / 6')).toBeTruthy();
  });

  it.each([
    ['one drawing', projectOneDrawing],
    ['pending', () => never()],
    ['failed', { status: 500, body: { detail: 'internal error', code: 'internal' } }],
  ])('EN-56 %s project: no arrows, no position; the screen works', async (_, body) => {
    open({ [DRAWING_ROUTE]: drawing, [PROJECT_ROUTE]: body });
    await screen.findByText('Ask a question about this drawing.');
    expect(screen.queryByRole('link', { name: /drawing$/ })).toBeNull();
    expect(screen.queryByText(/^\d+ \/ \d+$/)).toBeNull();
    expect(screen.getByRole('textbox', { name: 'Question' })).toBeTruthy();
  });

  it.each([
    [answer, 'One method', 'Only one method measured this; there is no second check.'],
    [
      answerAgree,
      'Two methods agree',
      'Two independent methods measured this and got the same value.',
    ],
    [
      answerConflict,
      'Methods disagree',
      'Two methods measured different values; the checks below say which one is kept and why.',
    ],
    [
      answerEstimate,
      'Estimate',
      'Measured with an estimated scale or method; treat it as approximate.',
    ],
    [answerEdited, 'Changed in review', 'A surveyor changed this value in review.'],
    [answerSigned, 'Verified', 'A surveyor checked this value and signed it off.'],
  ])('EN-57 the status pill %#: words, and its tooltip on focus', async (a, word, tip) => {
    const t = await shownTurn(a);
    // ui-bugs 7c: the shared Tip (components/ui/tip) on a focusable wrapper around the pill
    const pill = within(t).getByText(word, { selector: '.en-pill' });
    const trigger = pill.parentElement as HTMLElement;
    expect(screen.queryByRole('tooltip')).toBeNull();
    trigger.focus();
    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip.textContent).toBe(tip);
    expect(trigger.getAttribute('aria-describedby')).toBe(tooltip.id);
    fireEvent.keyDown(trigger, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  const chips = (t: HTMLElement) => [...t.querySelectorAll<HTMLElement>('.en-refs li')];

  it('EN-58 references: original file, the server proof, the second count; which are buttons', async () => {
    const t = await shownTurn(answer);
    const [one, two, three] = chips(t);
    expect(one?.textContent).toBe(
      '1Original fileplans/flat-a.pdfPDF vector reader read plans/flat-a.pdf (drawn PDF route), no second count',
    );
    expect(two?.textContent).toBe('2Proof drawn by the serverplans/flat-a.pdfPage 1 · marks 1–2');
    expect(three?.textContent).toBe('3Second countno second count');
    expect(one?.querySelector('button')).toBeTruthy();
    expect(two?.querySelector('button')).toBeTruthy();
    expect(three?.querySelector('button')).toBeNull();
  });

  it('EN-58 with a score the proof is no button; without the upload the original is none', async () => {
    const t = await shownTurn(answerConfidence);
    expect(chips(t)[1]?.querySelector('button')).toBeNull();
    cleanup();
    open({
      [DRAWING_ROUTE]: drawing,
      [PROJECT_ROUTE]: projectNoFiles,
      'POST /api/ask': answers(answer),
    });
    await typeAndAsk(answer.question);
    const u = await turn(answer.question);
    await within(u).findByTestId('answer-value');
    expect(chips(u)[0]?.querySelector('button')).toBeNull();
  });

  it('EN-59 the overlay: original file preview, focus to Close, Esc back to the chip; one at a time', async () => {
    const t = await shownTurn(answer);
    // The project arrives beside the drawing; the chip is a button once it has.
    const original = await within(t).findByRole('button', { name: /^1Original file/ });
    fireEvent.click(original);
    const dialog = within(t).getByRole('dialog', { name: 'Original file: plans/flat-a.pdf' });
    expect(within(dialog).getByRole('img').getAttribute('src')).toBe(previewUrl(PROJECT, 'f1'));
    expect(original.getAttribute('aria-pressed')).toBe('true');
    const close = within(dialog).getByRole('button', { name: 'Close the original' });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: 'Escape' });
    expect(within(t).queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(original);
    fireEvent.click(original);
    fireEvent.click(within(t).getByRole('button', { name: /^2Proof drawn/ }));
    const dialogs = within(t).getAllByRole('dialog');
    expect(dialogs).toHaveLength(1);
    expect(
      within(dialogs[0] as HTMLElement)
        .getByRole('img')
        .getAttribute('src'),
    ).toBe(evidenceUrl(DRAWING, answer.question, { project: PROJECT }));
  });

  it('EN-61 the ask box: Question, placeholder with the file, Ask; no edit-plan link', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('textbox', { name: 'Question' });
    expect(input().placeholder).toBe(`Ask about ${NAME}`);
    expect(askButton()).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Edit a house plan/ })).toBeNull();
  });

  it('EN-62 a refusal is a card: sentence, text, chips; no figure, value, references or footer', async () => {
    const t = await shownTurn(answerRefused);
    const card = t.querySelector('.v-card.en-refusal') as HTMLElement;
    expect(card.textContent).toContain("I can't answer that from this drawing.");
    expect(card.textContent).toContain(answerRefused.refusal?.text ?? '');
    expect(within(card).getAllByRole('button')).toHaveLength(
      answerRefused.refusal?.can_answer.length ?? 0,
    );
    expect(within(t).queryByRole('figure')).toBeNull();
    expect(within(t).queryByTestId('answer-value')).toBeNull();
    expect(within(t).queryByText('References')).toBeNull();
    expect(t.querySelector('footer')).toBeNull();
  });

  it.each([
    ['high', answerHigh, 'High'],
    ['medium', answerMedium, 'Medium'],
    ['low', answerLow, 'Low'],
  ])('EN-82 confidence %s from answer.level: the pill, the bar, level.text', async (_, a, word) => {
    // the double-check panel (check) has its own tests (EN-70); here only the confidence block
    const t = await shownTurn({ ...a, check: null });
    const block = t.querySelector('.en-grade') as HTMLElement;
    expect(within(block).getByText('Confidence')).toBeTruthy();
    expect(within(block).queryByText('Grade')).toBeNull();
    const pill = within(block).getByText(word);
    expect(pill.getAttribute('title')).toBeNull(); // the shared Tip, not a native title (ui-bugs 7c)
    (pill.parentElement as HTMLElement).focus();
    expect((await screen.findByRole('tooltip')).textContent).toBe(a.level?.text);
    fireEvent.keyDown(pill.parentElement as HTMLElement, { key: 'Escape' });
    // ui-bugs 7: the sentence under the bar is behind "Why?", closed by default
    const why = within(block).getByRole('button', { name: 'Why?' });
    expect(why.getAttribute('aria-expanded')).toBe('false');
    expect(within(block).getByText(a.level?.text ?? 'x').hidden).toBe(true);
    fireEvent.click(why);
    expect(within(block).getByText(a.level?.text ?? 'x').hidden).toBe(false);
    expect(t.textContent).not.toMatch(/Certified: on held-out|Sure check/);
    expect(within(t).queryByText(/^Sure/)).toBeNull();
  });

  it('EN-82 no level, no confidence block, whatever the score or line.sure', async () => {
    for (const a of [
      answer,
      answerConfidence,
      { ...answer, line: { ...answer.line, sure: true } },
    ]) {
      const t = await shownTurn(a);
      expect(t.querySelector('.en-grade')).toBeNull();
      cleanup();
    }
  });

  it('EN-83 signed off: "Signed off", no level; no double-check panel on a High answer', async () => {
    const signed = await shownTurn({ ...answerSigned, level: answerHigh.level });
    const block = signed.querySelector('.en-grade') as HTMLElement;
    expect(within(block).getByText('Signed off')).toBeTruthy();
    expect(within(block).queryByText('High')).toBeNull();
    expect(block.textContent).not.toContain(answerHigh.level?.text ?? 'x');
    expect(block.querySelector('.en-bar')).toBeNull();
  });

  it('EN-84 flagged drawing: flag reason and level at the top, above the plan and marks', async () => {
    // DoubleCheck reads this drawing's marks: the fixture's own drawing id has no route here
    const low: AnswerView = { ...answerLow, drawing_id: DRAWING };
    const flaggedProject = {
      ...project,
      drawings: project.drawings.map((d) =>
        d.drawing_id === DRAWING ? { ...d, state: 'flagged' as const } : d,
      ),
    };
    open({
      [PROJECT_ROUTE]: flaggedProject,
      [DRAWING_ROUTE]: drawing,
      'POST /api/ask': answers(low),
    });
    await typeAndAsk(low.question);
    const t = await turn(low.question);
    await within(t).findByText('This drawing was flagged');
    const flag = t.querySelector('.en-flag') as HTMLElement;
    expect(within(flag).getByText('This drawing was flagged')).toBeTruthy();
    expect(flag.textContent).toContain(answerLow.check?.reason ?? 'x');
    expect(within(flag).getByText('Low')).toBeTruthy();
    expect(flag.textContent).toContain(answerLow.level?.text ?? 'x');
    const card = t.querySelector('.en-card') as HTMLElement;
    const sentence = t.querySelector('.en-sentence') as HTMLElement;
    for (const later of [card, sentence]) {
      expect(flag.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    expect(t.querySelectorAll('.en-grade')).toHaveLength(1);
    expect(card.querySelector('.en-grade')).toBeNull();
    cleanup();
    const u = await shownTurn(low);
    expect(u.querySelector('.en-flag')).toBeNull();
    expect(u.querySelector('.en-card .en-grade')).toBeTruthy();
  });

  it('EN-85 a page-flagged answer (level.basis page) drops the counting rule from the sentence', async () => {
    const low: AnswerView = { ...answerLow, drawing_id: DRAWING, check: null };
    const t = await shownTurn(low);
    const rule = (low.quantity as Row).rule.text;
    expect(t.querySelector('.en-sentence')?.textContent).not.toContain(rule.slice(1));
    cleanup();
    const other: AnswerView = { ...low, level: { level: 'low', basis: 'score', text: 'Low.' } };
    const u = await shownTurn(other);
    expect(u.querySelector('.en-sentence')?.textContent).toContain(rule.slice(1));
  });

  it('EN-68 Row.noun: "There are 2 doors." with the noun after the value; null keeps the label sentence', async () => {
    const t = await shownTurn(answer);
    expect(t.querySelector('.en-noun')?.textContent).toBe('doors');
    expect(t.querySelector('[data-pending]')).toBeNull();
    cleanup();
    const none: AnswerView = { ...answer, quantity: { ...(answer.quantity as Row), noun: null } };
    const u = await shownTurn(none);
    expect(u.querySelector('.en-noun')).toBeNull();
    expect(u.querySelector('.en-sentence')?.textContent).toMatch(/^Door count: 2\. /);
  });

  it('EN-68 a sum has no noun: the label sentence', async () => {
    const t = await shownTurn(answerArea);
    expect(t.querySelector('.en-noun')).toBeNull();
    expect(t.querySelector('.en-sentence')?.textContent).toMatch(
      /^Area of room \(indoor\): 52\.27 m²\. /,
    );
  });

  it("EN-55 the meta passed to the viewer is kind and route only: storey and scale are the viewer's", async () => {
    const page = { ...(answer.pages[0] as AnswerView['pages'][number]), storey: 'Ground floor' };
    const t = await shownTurn({ ...answer, pages: [page] });
    const text = within(t).getByRole('figure', { name: 'Drawing' }).textContent;
    expect(text).toContain('PDF vector · drawn PDF route');
    expect(text.split('Ground floor')).toHaveLength(2);
    expect(text.split('1:100')).toHaveLength(2);
  });
});

describe('resolver (#252)', () => {
  // DoubleCheck reads this drawing's marks: give the fixture this page's drawing id
  const resolved: AnswerView = { ...answerResolved, drawing_id: DRAWING };
  const picked = resolved.resolved as NonNullable<AnswerView['resolved']>;

  it('RS-20 a pick beside the answer: value, level and check unchanged; never sure/high', async () => {
    const t = await shownTurn(resolved);
    expect(within(t).getByTestId('answer-value').textContent).toBe('2');
    expect(within(t.querySelector('.en-grade') as HTMLElement).getByText('Medium')).toBeTruthy();
    const line = t.querySelector('.en-resolved') as HTMLElement;
    expect(line.textContent).toContain('Picked by Carbon: 2');
    expect(line.textContent).toContain(picked.reason);
    expect(
      within(line)
        .getByText(/^Picked by Carbon/)
        .getAttribute('title'),
    ).toBe('gemini-4-carbon');
    expect(t.textContent).not.toMatch(/Sure|High|[Cc]ertified|gemini-4-carbon/);
  });

  it('RS-21 cannot_tell: "Carbon could not tell" and the reason', async () => {
    const t = await shownTurn({
      ...resolved,
      resolved: { ...picked, verdict: 'cannot_tell', value: null },
    });
    const line = t.querySelector('.en-resolved') as HTMLElement;
    expect(line.textContent).toContain('Carbon could not tell');
    expect(line.textContent).toContain(picked.reason);
    expect(line.textContent).not.toContain('Picked');
  });

  it('RS-22 resolver_note without resolved: a muted line; null: nothing', async () => {
    const t = await shownTurn({ ...resolved, resolved: null, resolver_note: 'Carbon counted 3.' });
    expect(t.querySelector('.en-resolvernote')?.textContent).toBe('Carbon counted 3.');
    expect(t.querySelector('.en-resolved')).toBeNull();
    cleanup();
    const u = await shownTurn({ ...resolved, resolved: null, resolver_note: null });
    expect(u.querySelector('.en-resolvernote, .en-resolved')).toBeNull();
  });
});

describe('judge path', () => {
  it('EN-86 the value row and the double-check come before the plan in the card (phones: above the fold)', async () => {
    const t = await shownTurn({ ...answerMedium, drawing_id: DRAWING });
    const head = t.querySelector('.en-card > .en-head') as HTMLElement;
    expect(within(head).getByTestId('answer-value')).toBeTruthy();
    expect(within(head).getByRole('region', { name: 'Double-check' })).toBeTruthy();
    const fig = t.querySelector('.en-card > .en-left') as HTMLElement;
    expect(head.compareDocumentPosition(fig) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(t.querySelector('.en-card > .en-side .en-grade')).toBeTruthy();
  });

  it("EN-87 one name: the page title and ask box use the project's drawing name", async () => {
    await shownTurn(answer);
    const name = drawingLabel(
      project.drawings.find((d) => d.drawing_id === DRAWING) ?? { file: '' },
    );
    expect(name).not.toBe(drawing.file);
    expect(input().placeholder).toBe(`Ask about ${name}`);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(name);
    // the viewer's title line too (the plan is what the judge looks at)
    expect(document.querySelector('.vw-name')?.textContent).toBe(name);
  });

  it('EN-88 an estimated area shows "about <n> m², <estimate>" under the value', async () => {
    const q = answerArea.quantity as Row;
    const t = await shownTurn({
      ...answerArea,
      answer: 179.6,
      quantity: { ...q, estimate: 'the scale estimated from the doors' },
    });
    expect(t.querySelector('.en-head .en-estimate')?.textContent).toBe(
      'about 180 m², the scale estimated from the doors',
    );
  });

  it('CH-48 the answer card says an estimated area as the chat does: 5 m² in the sentence, the value and the caveat', async () => {
    // the Finnish flat's kitchen as the API sends it (#294): measured 4.88 m², shown in whole m²
    const q = answerArea.quantity as Row;
    const why = 'the scale estimated from the doors';
    const t = await shownTurn({
      ...answerArea,
      answer: 5,
      quantity: { ...q, value: 4.88, original_value: 4.88, estimate: why },
    });
    expect(within(t).getByTestId('answer-value').textContent).toBe('5 m²');
    expect(t.querySelector('.en-sentence strong')?.textContent).toBe('5 m²');
    expect(t.querySelector('.en-head .en-estimate')?.textContent).toBe(`about 5 m², ${why}`);
    expect(t.textContent).not.toMatch(/4\.88|5\.00/);
  });

  it('EN-90 a partial room total has a tag beside its value with the counts', async () => {
    const t = await shownTurn({
      ...answer,
      partial: true,
      rooms_counted: 7,
      rooms_missing: ['Sauna', 'WC 2'],
    });
    const tag = t.querySelector('.en-head .en-value-row .en-partial');
    expect(tag?.textContent).toBe('May be partial');
    expect(tag?.getAttribute('aria-label')).toBe('May be partial: sums 7 rooms; 2 not in it');
  });

  it('EN-90 no partial tag when partial is absent', async () => {
    const t = await shownTurn(answer);
    expect(t.querySelector('.en-partial')).toBeNull();
  });

  it('EN-89 a double-check reason that already gives the estimate is the one line: no estimate line', async () => {
    const why = 'counted by Gemini Carbon, an AI reader: check its marks on the plan';
    const reason = `Please double-check the doors: it is an estimate (${why}).`;
    const q = answerMedium.quantity as Row;
    const check = answerMedium.check as NonNullable<typeof answerMedium.check>;
    const carbon = {
      ...answerMedium,
      drawing_id: DRAWING,
      answer: 19,
      quantity: { ...q, estimate: why },
      check: { ...check, reason },
    };
    let t = await shownTurn(carbon);
    expect(t.querySelector('.dc-reason')?.textContent).toBe(reason);
    expect(t.querySelector('.en-estimate')).toBeNull();
    cleanup();
    // High: no double-check panel, so the reason is not shown and the caveat stays
    const high = {
      ...carbon,
      level: { ...(carbon.level as NonNullable<typeof carbon.level>), level: 'high' as const },
    };
    t = await shownTurn(high);
    expect(t.querySelector('.dc-reason')).toBeNull();
    expect(t.querySelector('.en-estimate')?.textContent).toBe(
      'Counted by Gemini Carbon, an AI reader: check its marks on the plan',
    );
  });
});

describe('hover tips on the engineer page (docs/ui-tooltips.md)', () => {
  /** Focus the tip's trigger (the nearest focusable wrapper) and wait for its words. */
  async function tipOf(el: HTMLElement, text: string) {
    (el.closest('[tabindex]') as HTMLElement).focus();
    expect((await screen.findAllByText(text)).length).toBeGreaterThan(0);
  }

  it('the "how it was read" line says what it is', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    const line = await screen.findByText(/^(.*), read from /);
    await tipOf(line, TIPS.howRead);
  });

  it('a suggested question says what the chips are', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    const chip = await screen.findByRole('button', { name: drawing.suggestions[0]?.question });
    chip.focus();
    expect((await screen.findAllByText(new RegExp(TIPS.suggested))).length).toBeGreaterThan(0);
  });

  it('the greyed-out send button says why: type a question first', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    const send = await screen.findByRole('button', { name: 'Ask' });
    expect(send).toHaveProperty('disabled', true);
    await tipOf(send, TIPS.sendDisabled);
  });

  it('the checks, second reader score and counting rule explain themselves', async () => {
    const t = await shownTurn(scoredAgree);
    await tipOf(within(t).getByText('Checks'), TIPS.checks);
    await tipOf(within(t).getByText(/^Second reader's score/), TIPS.secondScore);
    await tipOf(within(t).getByText(/^Counting rule:/), TIPS.rule);
  });

  it('the flagged box says what a flag means', async () => {
    const low: AnswerView = { ...answerLow, drawing_id: DRAWING };
    const flaggedProject = {
      ...project,
      drawings: project.drawings.map((d) =>
        d.drawing_id === DRAWING ? { ...d, state: 'flagged' as const } : d,
      ),
    };
    open({
      [PROJECT_ROUTE]: flaggedProject,
      [DRAWING_ROUTE]: drawing,
      'POST /api/ask': answers(low),
    });
    await typeAndAsk(low.question);
    const t = await turn(low.question);
    await tipOf(await within(t).findByText('This drawing was flagged'), TIPS.flagged);
  });
});

describe('a text answer from a building model (deep QA, research-lead 1)', () => {
  const text = '5 storeys:\n- Basement: elevation -3.00 m\n- Ground floor: elevation 0.00 m';
  const facts = (answerText: string): AnswerView => ({
    ...answerModel,
    question: 'How many storeys does the building have?',
    answer: answerText,
    unit: null,
    quantity: null,
    marks: [],
    method: 'facts',
    proof: { ...answerModel.proof, kind: 'none', arithmetic: null, objects: null, storeys: null },
  });

  it('is set as text with its lines kept, not as the big value; its first line is the sentence', async () => {
    const a = facts(text);
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(a) });
    await typeAndAsk(a.question);
    const t = await turn(a.question);
    const value = await within(t).findByTestId('answer-value');
    expect(value.className).toBe('en-value en-value--text');
    expect(value.textContent).toBe(text);
    expect(t.querySelector('.en-sentence')?.textContent).toBe('5 storeys.');
    // the drawing pane is not left empty
    expect(within(t).getByText('Read from the model data: no sheet to point at.')).toBeTruthy();
  });

  it('a short text answer stays the big value', async () => {
    const a = facts('Kitchen');
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(a) });
    await typeAndAsk(a.question);
    const value = await within(await turn(a.question)).findByTestId('answer-value');
    expect(value.className).toBe('en-value');
  });
});
