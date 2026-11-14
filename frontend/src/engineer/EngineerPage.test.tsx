import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { methodName, type AnswerView } from '../api';
import {
  answer,
  answerArea,
  answerConfidence,
  answerModel,
  answerRefused,
  drawing,
  error,
  info,
} from '../api/fixtures';
import { InfoProvider } from '../shell/info';
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
  answerUnlocated,
  answerWithMarkup,
  drawingHello,
  drawingNoSuggestions,
  markup,
  refusalWithMarkup,
} from './testing';

const PROJECT = '5e0c1a2b3d4f';
const DRAWING = drawing.id;
const DRAWING_ROUTE = `GET /api/drawings/${DRAWING}`;

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
  const api = mockApi(routes);
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
});

afterEach(() => {
  cleanup();
});

describe('drawing header and ask box', () => {
  it('R1-PS-1 EN-49 the drawing is requested in the route project', async () => {
    const api = open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('heading', { name: drawing.file });
    expect(api.calls.map((c) => c.url)).toEqual([`/api/drawings/${DRAWING}?project=${PROJECT}`]);
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
    await screen.findByRole('heading', { name: 'plans/flat-a.pdf' });
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
    expect(screen.getAllByText(/not-found/).length).toBeGreaterThan(0);
    const back = screen.getByRole('link', { name: 'Back to the project' });
    expect(back.getAttribute('href')).toBe(`#/p/${PROJECT}`);
  });

  it('EN-4 the header shows the file and how it was read', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    expect(await screen.findByRole('heading', { name: 'plans/flat-a.pdf' })).toBeTruthy();
    expect(
      screen.getByText(
        'vector route, read from plans/flat-a.pdf by PDF vector reader; second count: PDF vector reader; questions: question templates',
      ),
    ).toBeTruthy();
  });

  it('QA #76 EN-4 a header without a second count says so', async () => {
    open({
      [DRAWING_ROUTE]: { ...drawing, reader: { ...drawing.reader, second_counter: 'none' } },
    });
    expect(
      await screen.findByText(
        'vector route, read from plans/flat-a.pdf by PDF vector reader; no second count; questions: question templates',
      ),
    ).toBeTruthy();
  });

  it('EN-6 one button per suggestion, in order', async () => {
    open({ [DRAWING_ROUTE]: drawing });
    await screen.findByRole('heading', { name: 'plans/flat-a.pdf' });
    const header = screen.getByRole('region', { name: 'Drawing' });
    const names = within(header)
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
    expect(within(t).getByText('Reading plans/flat-a.pdf…')).toBeTruthy();
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
    expect(within(t).getByText('door count')).toBeTruthy();
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

  it('EN-18 the counting rule', async () => {
    const t = await shown(answer);
    expect(
      within(t).getByText(
        'Counting rule: every element, room and plan the drawing lists counts once',
      ),
    ).toBeTruthy();
  });

  it('EN-20 the viewer gets the proof legend: one colour per room label', async () => {
    const t = await shown(answerArea);
    const html = t.innerHTML;
    expect(html).toContain('#d62728');
    expect(html).toContain('#1f77b4');
  });

  it("QA R1 EN-23 the second reader's score, no signal name on the card, never a probability", async () => {
    const conf = answerConfidence.confidence;
    expect(conf).not.toBeNull();
    const signal = conf?.signal ?? '';
    const t = await shown(answerConfidence);
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
    expect(within(t).queryByRole('link')).toBeNull();
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
    expect(within(t).getByText(/validation/)).toBeTruthy();
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
    await within(t).findByText('Reading plans/flat-a.pdf…');
    const before = scroll.mock.calls.length;
    arrive(answerArea);
    await within(t).findByTestId('answer-value');
    expect(scroll.mock.calls.length).toBeGreaterThan(before);
    expect(scroll.mock.contexts.at(-1)).toBe(t);
  });

  it('R2 qa-3 EN-52 the folded suggestions and Details keep the disclosure marker', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    await askSuggestion(answer.question);
    const t = await turn(answer.question);
    await within(t).findByTestId('answer-value');
    const header = screen.getByRole('region', { name: 'Drawing' });
    const fold = within(header).getByText('Suggested questions');
    expect(fold.tagName).toBe('SUMMARY');
    expect(fold.style.display).toBe('list-item');
    const details = within(t).getByText('Details');
    expect(details.tagName).toBe('SUMMARY');
    expect(details.style.display).toBe('list-item');
  });

  it('review fix 2: after the first answer the suggestions fold into a closed details', async () => {
    open({ [DRAWING_ROUTE]: drawing, 'POST /api/ask': answers(answer) });
    const header = await screen.findByRole('region', { name: 'Drawing' });
    expect(within(header).queryByText('Suggested questions')).toBeNull();
    await askSuggestion('How many doors are there?');
    await within(await turn('How many doors are there?')).findByTestId('answer-value');
    const fold = within(header).getByText('Suggested questions').closest('details');
    expect(fold?.open).toBe(false);
    expect(within(fold as HTMLElement).getAllByRole('button', { hidden: true })).toHaveLength(
      drawing.suggestions.length,
    );
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
        'PDF vector reader read plans/flat-a.pdf (vector route), no second count',
      ),
    ).toBeTruthy();
    cleanup();
    const counted = await shownTurn({
      ...answer,
      reader: { ...answer.reader, second_counter: 'ifc' },
    });
    expect(
      within(counted).getByText(
        'PDF vector reader read plans/flat-a.pdf (vector route), second count by IFC model',
      ),
    ).toBeTruthy();
  });

  it('EN-27 details are collapsed, with the query and method; no How line when null', async () => {
    const t = await shownTurn(answer);
    const details = within(t).getByText('Details').closest('details');
    expect(details?.open).toBe(false);
    const inside = within(details as HTMLElement);
    expect(inside.getByText('Query: door')).toBeTruthy();
    expect(inside.getByText('Method: takeoff')).toBeTruthy();
    expect(inside.queryByText(/^How:/)).toBeNull();
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
    const header = await screen.findByRole('region', { name: 'Drawing' });
    expect(header.textContent).toContain('not read (no reader for this route yet)');
    expect(header.textContent).not.toContain('by hello');
    expect(
      screen.getByText('Its route has no reader yet, so questions will be refused.'),
    ).toBeTruthy();
  });

  it('EN-7 no suggestions: the sentence and the ask box', async () => {
    open({ [DRAWING_ROUTE]: drawingNoSuggestions });
    expect(await screen.findByText('No ready questions for this drawing.')).toBeTruthy();
    expect(screen.getByRole('textbox', { name: 'Question' })).toBeTruthy();
  });

  it('EN-11 the question length limit from /api/info', async () => {
    mockApi({ 'GET /api/info': info, [DRAWING_ROUTE]: drawing });
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
