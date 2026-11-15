// chat.md "Demo parity": the chat's answer card (CH-30..CH-35), PageViewer mocked to read what it gets.
import type { ComponentProps } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { ProjectAnswer, ProjectView } from '../api';
import { drawingLabel } from '../api';
import { answer, answerArea, answerResolved, project, projectAsk } from '../api/fixtures';
import { routeLabel } from '../ingest/ingest';
import type { PageViewer } from '../viewer/PageViewer';
import { ChatAnswer } from './ChatAnswer';
import { answerHigh, answerMedium } from './testing';
import { kindName } from './format';

type ViewerProps = ComponentProps<typeof PageViewer>;
const viewers: ViewerProps[] = [];
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: ViewerProps) => {
    viewers.push(props);
    return <div data-testid="viewer">{props.file}</div>;
  },
}));

vi.mock('../model3d/ModelDialog', () => ({
  ModelDialog: (props: { label: string }) => (
    <div role="dialog" aria-label={`3D: ${props.label}`} />
  ),
}));

type Part = ProjectAnswer['parts'][number];
const [flatA, flatB] = projectAsk.parts as [Part, Part, Part];
// projectWith() gives the parts project.json's first two drawings, so their #224 names (CH-40)
const LA = drawingLabel(project.drawings[0] ?? { file: '' });
const LB = drawingLabel(project.drawings[1] ?? { file: '' });

/** project.json whose first two drawings are the answering parts' (the fixtures use different ids). */
function projectWith(triagedB: 'other_drawing' | null): ProjectView {
  const [d0, d1] = project.drawings as [ProjectView['drawings'][0], ProjectView['drawings'][0]];
  const [f0] = project.files as [ProjectView['files'][0]];
  const triage = triagedB && { ...(f0.triage ?? {}), class: triagedB };
  return {
    ...project,
    drawings: [
      { ...d0, drawing_id: flatA.drawing_id, file: flatA.name },
      { ...d1, drawing_id: flatB.drawing_id, file: flatB.name, kind: 'png_plan', route: 'raster' },
    ],
    files: [
      { ...f0, id: 'f1', drawing_id: flatA.drawing_id, path: flatA.name, triage: null },
      {
        ...f0,
        id: 'f2',
        drawing_id: flatB.drawing_id,
        path: flatB.name,
        triage: triage as ProjectView['files'][0]['triage'],
      },
    ],
  };
}

function show(ask: ProjectAnswer = projectAsk, proj: ProjectView = projectWith(null)) {
  // a fresh object per render: the picked reference is kept per answer object (qa #430 item 3)
  render(<ChatAnswer ask={{ ...ask }} project={proj} projectId={project.id} pack={null} />);
}
const refs = () =>
  within(screen.getByRole('list', { name: 'References' })).getAllByRole('listitem');
const rows = () =>
  within(screen.getByRole('list', { name: 'Per drawing' })).getAllByRole('listitem');
/** The one card shown (ui-bugs 6) after choosing reference n. */
const rowAt = (n: number) => {
  fireEvent.click(within(refs()[n] as HTMLElement).getByRole('button'));
  expect(rows()).toHaveLength(1);
  return rows()[0] as HTMLElement;
};
const figure = () => screen.getByRole('figure', { name: /^Reference / });

beforeAll(() => {
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
  viewers.length = 0;
});

it('CH-30 a sheet that is not a floor plan comes first, in the rows and the references alike', () => {
  show(projectAsk, projectWith('other_drawing'));
  expect(rows()[0]?.textContent).toContain(LB);
  expect(refs()[0]?.textContent).toContain(LB);
  expect(rowAt(1).textContent).toContain(LA);
  cleanup();
  show(projectAsk, projectWith(null));
  expect(rows()[0]?.textContent).toContain(LA);
  expect(refs()[0]?.textContent).toContain(LA);
});

it('CH-31 the lead: why_no_total without a total, never the refused drawings; a total with its note', () => {
  show();
  expect(screen.getByText(projectAsk.why_no_total ?? 'x')).toBeTruthy();
  expect(screen.queryByText(projectAsk.refused_note ?? 'x', { exact: false })).toBeNull();
  expect(screen.queryByText(projectAsk.total_note)).toBeNull();
  expect(screen.queryByTestId('answer-value')).toBeNull();
  cleanup();
  show({ ...projectAsk, why_no_total: null });
  expect(screen.getByText(projectAsk.total_note)).toBeTruthy();
  cleanup();
  const total = { ...projectAsk, total: 4, total_unit: 'count' as const, why_no_total: null };
  show({ ...total, total_note: 'Two floors.', refused_note: null });
  const value = screen.getByTestId('answer-value');
  expect(value.textContent).toBe('4 doors');
  expect(value.closest('strong, .en-lead')).toBeTruthy();
  expect(screen.queryByText('Two floors.')).toBeNull(); // CH-39: the lead is the value only
  cleanup();
  show({
    ...total,
    total_note: 'Two floors; 1 drawing gives no reliable number for it.',
    refused_note: '1 drawing gives no reliable number for it.',
  });
  expect(screen.getByTestId('answer-value').textContent).toBe('4 doors');
  expect(document.body.textContent).not.toContain('no reader');
});

it('K7 the drawings that refused are named with what each lacks, under the card', () => {
  show();
  const line = screen.getByTestId('refused-drawings');
  expect(line.textContent).toBe('Not used: ground-floor.png gives no reliable number for it.');
  cleanup();
  show({ ...projectAsk, parts: projectAsk.parts.slice(0, 2) });
  expect(screen.queryByTestId('refused-drawings')).toBeNull();
});

it('CH-32 reference 1 is drawn large by the viewer with its marks and legend; no credit', () => {
  show();
  expect(figure().getAttribute('aria-label')).toBe('Reference 1 of 2');
  const v = viewers.at(-1);
  expect(v?.file).toBe(flatA.name);
  expect(v?.pages).toEqual(flatA.answer.pages);
  expect(v?.marks).toEqual(flatA.answer.marks);
  expect(v?.legend).toEqual(flatA.answer.proof.legend);
  expect(v?.credit).toBeNull();
  expect(document.body.textContent).not.toMatch(/Credit/);
});

it('CH-33 ui-bugs 4: no arrows on the image; the references switch it and sit under it in the figure', () => {
  show();
  expect(screen.queryByRole('button', { name: /reference$/ })).toBeNull();
  expect(figure().contains(screen.getByRole('list', { name: 'References' }))).toBe(true);
  expect(
    screen
      .getByTestId('viewer')
      .compareDocumentPosition(screen.getByRole('list', { name: 'References' })),
  ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  // W2: the one drawing card sits between the image and the references, in the same column
  const card = screen.getByRole('list', { name: 'Per drawing' });
  expect(figure().contains(card)).toBe(true);
  expect(screen.getByTestId('viewer').compareDocumentPosition(card)).toBe(
    Node.DOCUMENT_POSITION_FOLLOWING,
  );
  expect(card.compareDocumentPosition(screen.getByRole('list', { name: 'References' }))).toBe(
    Node.DOCUMENT_POSITION_FOLLOWING,
  );
  fireEvent.click(within(refs()[1] as HTMLElement).getByRole('button'));
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  expect(viewers.at(-1)?.file).toBe(flatB.name);
});

it('CH-34 the references: numbered buttons, kind and route in words, the current one pressed', () => {
  show(projectAsk, projectWith(null));
  const [one, two] = refs() as [HTMLElement, HTMLElement];
  const b1 = within(one).getByRole('button');
  const b2 = within(two).getByRole('button');
  expect(b1.textContent).toContain('1');
  expect(b1.textContent).toContain(LA);
  expect(b1.textContent).toContain(`${kindName('pdf_vector')} · ${routeLabel('vector')}`);
  expect(b2.textContent).toContain(`${kindName('png_plan')} · ${routeLabel('raster')}`);
  expect(b1.getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(b2);
  expect(b2.getAttribute('aria-pressed')).toBe('true');
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  cleanup();
  // ui-bugs 6: a building model has no page: "no preview", and chosen it shows its card and a placeholder
  show({ ...projectAsk, parts: [flatA, { ...flatB, answer: { ...flatB.answer, pages: [] } }] });
  const model = refs()[1] as HTMLElement;
  expect(model.textContent).toContain('no preview');
  expect(figure().getAttribute('aria-label')).toBe('Reference 1 of 2');
  expect(screen.queryByText('No preview for this file')).toBeNull();
  const n = viewers.length;
  expect(rowAt(1).textContent).toContain(LB);
  expect(screen.getByText('No preview for this file')).toBeTruthy();
  expect(screen.queryByTestId('viewer')).toBeNull();
  expect(viewers.length).toBe(n);
});

it('CH-35 ui-bugs 6/8: only the card of the shown drawing, its value and status, no Show it on link; nothing for a refused one', () => {
  show();
  expect(rows()).toHaveLength(1);
  const [a] = rows() as [HTMLElement];
  expect(a.textContent).toContain(`${LA}: 2`);
  expect(a.textContent).toContain('One method');
  expect(screen.queryByRole('link', { name: /^Show it on/ })).toBeNull();
  expect(rowAt(1).textContent).toContain(`${LB}:`);
  const refused = projectAsk.parts[2]?.name ?? '';
  expect(document.body.textContent).not.toContain(refused);
});

it('CH-39 the lead is the bold value only; without a total the why sentence, smaller; no label line', () => {
  const total = { ...projectAsk, total: 2, total_unit: 'count' as const, why_no_total: null };
  show({ ...total, total_note: 'Over one drawing.', refused_note: null });
  const lead = document.querySelector('.en-lead') as HTMLElement;
  expect(within(lead).getByTestId('answer-value').closest('strong')).toBeTruthy();
  expect(lead.textContent).toMatch(/^2 doors/);
  expect(screen.queryByText('Over one drawing.')).toBeNull();
  expect(screen.queryByText(/^Door count$/)).toBeNull();
  cleanup();
  show();
  const why = screen.getByText(projectAsk.why_no_total ?? 'x');
  expect(why.classList.contains('en-lead--why')).toBe(true);
});

it('CH-39 the viewer is bare; each row is one sentence with the value in bold, one pill and the link', () => {
  show();
  expect(viewers.at(-1)?.bare).toBe(true);
  // bare drops the viewer's own name: the card prints it, mono, above the image
  const name = figure().querySelector('.en-chatname');
  expect(name?.textContent).toBe(LA);
  expect(name?.compareDocumentPosition(screen.getByTestId('viewer'))).toBe(
    Node.DOCUMENT_POSITION_FOLLOWING,
  );
  const [a] = rows() as [HTMLElement];
  expect(a.querySelector('strong')?.textContent).toMatch(/^2/);
  expect(a.querySelectorAll('.v-pill')).toHaveLength(1);
  cleanup();
  show({
    ...projectAsk,
    parts: [{ ...flatA, answer: { ...flatA.answer, level: answerHigh.level } }],
  });
  const [sure] = rows() as [HTMLElement];
  expect(
    [...sure.querySelectorAll('.v-pill')].map((x) => x.textContent.replace(/\..*/, '')),
  ).toEqual(['High confidence']);
});

it('CH-40 drawings by their plain name (#224), files by their path; a part not in the project by its file name', () => {
  expect(LA).toBe('Drawn plan 1');
  show();
  const [a] = rows() as [HTMLElement];
  expect(a.textContent).toContain('Drawn plan 1: 2 doors');
  // CH-41: the figure's title and the references by the drawing's name too
  expect(refs()[0]?.textContent).toContain('Drawn plan 1');
  expect(refs()[0]?.textContent).not.toContain(flatA.name);
  expect(figure().querySelector('.en-chatname')?.textContent).toBe('Drawn plan 1');
  cleanup();
  show(projectAsk, { ...project, drawings: [], files: [] });
  expect(rows()[0]?.textContent).toContain('flat-a.pdf: 2 doors');
});

it('CH-42 one pill per row: Signed off, else the level with its text, else the status; the total level', async () => {
  const signed = { ...flatB.answer, level: answerHigh.level };
  if (!signed.quantity) throw new Error('flat-b has a quantity');
  signed.quantity = { ...signed.quantity, status: 'signed' };
  show({
    ...projectAsk,
    parts: [
      { ...flatA, answer: { ...flatA.answer, level: answerMedium.level } },
      { ...flatB, answer: signed },
    ],
  });
  const a = rowAt(0); // the higher level opens first (QA-1): choose reference 1
  const pill = a.querySelector('.v-pill') as HTMLElement;
  expect(pill.textContent).toBe('Medium confidence');
  expect(pill.getAttribute('title')).toBeNull();
  // ui-bugs 7c: the level's sentence is the shared Tip's, on focus or hover
  (pill.parentElement as HTMLElement).focus();
  expect((await screen.findByRole('tooltip')).textContent).toBe(answerMedium.level?.text);
  expect(rowAt(1).querySelector('.v-pill')?.textContent).toBe('Signed off');
  expect(document.body.textContent).not.toMatch(/Sure/);
  cleanup();
  show({ ...projectAsk, total: 4, total_unit: 'count', total_level: 'low', total_sure: true });
  const lead = document.querySelector('.en-lead') as HTMLElement;
  expect(lead.textContent).toContain('Low confidence');
  expect(lead.textContent).not.toContain('Sure');
  cleanup();
  show({ ...projectAsk, total: 4, total_unit: 'count', total_level: null });
  expect((document.querySelector('.en-lead') as HTMLElement).querySelector('.v-pill')).toBeNull();
});

it('RS-23 the chat rows show the pick, cannot_tell and resolver_note lines as the answer card', () => {
  const picked = answerResolved.resolved as NonNullable<typeof answerResolved.resolved>;
  show({
    ...projectAsk,
    parts: [
      { ...flatA, answer: { ...flatA.answer, unit: 'count', resolved: picked } },
      { ...flatB, answer: { ...flatB.answer, resolved: null, resolver_note: 'Carbon counted 3.' } },
    ],
  });
  const a = rows()[0] as HTMLElement;
  expect(a.querySelector('.en-resolved')?.textContent).toContain(
    `Picked by Carbon: 2. ${picked.reason}`,
  );
  expect(rowAt(1).querySelector('.en-resolvernote')?.textContent).toBe('Carbon counted 3.');
  expect(document.body.textContent).not.toMatch(/gemini-4-carbon/);
  cleanup();
  show({
    ...projectAsk,
    parts: [
      {
        ...flatA,
        answer: { ...flatA.answer, resolved: { ...picked, verdict: 'cannot_tell', value: null } },
      },
    ],
  });
  expect(rows()[0]?.querySelector('.en-resolved')?.textContent).toContain('Carbon could not tell');
});

it('CH-43 ui-bugs 7: check.reason stays under the value; the confidence sentence only behind "Why?"', () => {
  show({
    ...projectAsk,
    parts: [
      { ...flatA, answer: answerMedium },
      { ...flatB, answer: { ...answerHigh, check: null } },
    ],
  });
  const a = rowAt(0); // the higher level opens first (QA-1): choose reference 1
  expect(a.querySelector('.en-why')?.textContent).toBe(answerMedium.check?.reason);
  const b = rowAt(1);
  expect(b.querySelector('.en-why')).toBeNull();
  const text = answerHigh.level?.text ?? 'x';
  const toggle = within(b).getByRole('button', { name: 'Why?' });
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  expect(within(b).getByText(text).hidden).toBe(true);
  fireEvent.click(toggle);
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  expect(within(b).getByText(text).hidden).toBe(false);
  fireEvent.click(toggle);
  expect(within(b).getByText(text).hidden).toBe(true);
  cleanup();
  show({ ...projectAsk, parts: [{ ...flatA, answer: { ...answer, check: null, level: null } }] });
  expect(rows()[0]?.querySelector('.en-why')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Why?' })).toBeNull();
});

it('CH-44 an estimated value adds "about <n> <unit>, <estimate>" under the row', () => {
  const est = {
    ...answerArea,
    answer: 179.6,
    quantity: {
      ...(answerArea.quantity as NonNullable<typeof answerArea.quantity>),
      estimate: 'the scale estimated from the doors',
    },
  };
  show({
    ...projectAsk,
    parts: [
      { ...flatA, answer: est },
      { ...flatB, answer: answerArea },
    ],
  });
  const a = rows()[0] as HTMLElement;
  expect(a.querySelector('.en-estimate')?.textContent).toBe(
    'about 180 m², the scale estimated from the doors',
  );
  expect(rowAt(1).querySelector('.en-estimate')).toBeNull();
});

it('CH-46 a check reason that already gives the estimate is the one line: no estimate line under it', () => {
  const why = 'read from the plan by Carbon';
  const q = answerMedium.quantity as NonNullable<typeof answerMedium.quantity>;
  const check = answerMedium.check as NonNullable<typeof answerMedium.check>;
  const est = {
    ...answerMedium,
    answer: 19,
    quantity: { ...q, estimate: why },
    check: { ...check, reason: `Please double-check the doors: it is an estimate (${why}).` },
  };
  show({ ...projectAsk, parts: [{ ...flatA, answer: est }] });
  const row = rows()[0] as HTMLElement;
  expect(row.querySelector('.en-why')?.textContent).toBe(
    `Please double-check the doors: it is an estimate (${why}).`,
  );
  expect(row.querySelector('.en-estimate')).toBeNull();
  expect(row.textContent).not.toContain('about 19');
});

/** The Finnish flat's kitchen as the API sends it (#294): measured 4.88 m² on an estimated scale, shown in whole m². */
const KITCHEN_WHY = 'the scale estimated from the doors';
const kitchen = {
  ...answerArea,
  answer: 5,
  quantity: {
    ...(answerArea.quantity as NonNullable<typeof answerArea.quantity>),
    value: 4.88,
    original_value: 4.88,
    estimate: KITCHEN_WHY,
  },
};
/** Every number printed in an element's text. */
const numbers = (el: Element) => el.textContent.match(/\d+(?:\.\d+)?/g) ?? [];

it('CH-48 an estimated area reads one number everywhere: lead, row and estimate line say 5 m², never 4.88 or 5.00', () => {
  const ask: ProjectAnswer = {
    ...projectAsk,
    parts: [{ ...flatA, answer: kitchen }],
    total: 5, // the backend's _total: whole m² when a summed part is an estimate
    total_unit: 'm2',
    why_no_total: null,
  };
  show(ask);
  expect(screen.getByTestId('answer-value').textContent).toBe('5 m²');
  const [row] = rows() as [HTMLElement];
  expect(row.textContent).toContain(`${LA}: 5 m²`);
  expect(row.querySelector('.en-estimate')?.textContent).toBe(`about 5 m², ${KITCHEN_WHY}`);
  const lead = screen.getByTestId('answer-value');
  // the drawing's name ("Drawn plan 1") carries a number too: only the value's numbers count
  const values = [...numbers(lead), ...numbers(row).filter((n) => !LA.includes(n))];
  expect(new Set(values)).toEqual(new Set(['5']));
});

it('CH-48 a measured (not estimated) area keeps its two decimals in the lead and the row', () => {
  const plain = { ...kitchen, answer: 4.88, quantity: { ...kitchen.quantity, estimate: null } };
  show({
    ...projectAsk,
    parts: [{ ...flatA, answer: plain }],
    total: 4.88,
    total_unit: 'm2',
    why_no_total: null,
  });
  expect(screen.getByTestId('answer-value').textContent).toBe('4.88 m²');
  expect((rows()[0] as HTMLElement).textContent).toContain(`${LA}: 4.88 m²`);
});

it('CH-48 a printed-table answer (no quantity) still shows its own answer', () => {
  const table = { ...answerArea, answer: 12, unit: 'count' as const, quantity: null };
  show({ ...projectAsk, parts: [{ ...flatA, answer: table }], total: null });
  const [row] = rows() as [HTMLElement];
  expect(row.textContent).toContain(`${LA}: 12`);
});

it('CH-49 a partial room total: one tag beside that row value with the counts, none on the other rows', async () => {
  const partial = {
    ...flatA,
    answer: { ...flatA.answer, partial: true, rooms_counted: 7, rooms_missing: ['Sauna', 'WC 2'] },
  };
  show({ ...projectAsk, parts: [partial, ...projectAsk.parts.slice(1)] });
  const tags = [...(rows()[0] as HTMLElement).querySelectorAll('.en-partial')];
  expect(rowAt(1).querySelector('.en-partial')).toBeNull();
  fireEvent.click(within(refs()[0] as HTMLElement).getByRole('button'));
  expect(
    tags.map((t) => [t.textContent, t.getAttribute('aria-label'), t.getAttribute('title')]),
  ).toEqual([
    [
      'May be partial',
      'May be partial: sums 7 rooms; 2 not in it',
      null, // the words are the shared Tip's now, not a native title
    ],
  ]);
  expect(rows()[0]?.textContent).not.toContain('Sauna'); // the names are the explanation's to give
  (rows()[0]?.querySelector('.en-partial')?.closest('[tabindex]') as HTMLElement).focus();
  expect(
    (await screen.findAllByText('May be partial: sums 7 rooms; 2 not in it')).length,
  ).toBeGreaterThan(0);
});

it('CH-49 nothing when no part is partial', () => {
  show();
  expect(document.querySelector('.en-partial')).toBeNull();
});

it('W3 the round "3D" button only when the shown drawing has a model; a 2D drawing names the building model', () => {
  const ready = { state: 'ready' as const, reason: '', elements: 6 };
  const base = projectWith(null);
  const [d0, d1] = base.drawings as [ProjectView['drawings'][0], ProjectView['drawings'][0]];
  const proj = { ...base, drawings: [d0, { ...d1, kind: 'ifc' as const }] };
  const bim = {
    ...flatB,
    answer: { ...flatB.answer, pages: [] },
    model_file_id: 'f8',
    model_3d: ready,
  };
  show({ ...projectAsk, parts: [flatA, bim] }, proj);
  // the shown 2D plan has no model of its own: no button, though the answer has a building model
  expect(screen.queryByRole('button', { name: /in 3D/ })).toBeNull();
  fireEvent.click(within(refs()[1] as HTMLElement).getByRole('button'));
  const open = screen.getByRole('button', { name: `View in 3D: ${LB}` });
  expect(open.textContent).toBe('3D');
  expect(open.closest('.en-chathead')).toBeTruthy();
  fireEvent.click(open);
  expect(screen.getByRole('dialog', { name: `3D: ${LB}` })).toBeTruthy();
  cleanup();
  // a 2D drawing linked to the building's model: the button says it is the building model
  const linked = { ...flatA, model_file_id: 'f8', model_3d: ready };
  show({ ...projectAsk, parts: [linked, bim] }, proj);
  expect(screen.getByRole('button', { name: 'View the building model in 3D' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: /^View in 3D/ })).toBeNull();
  cleanup();
  show();
  expect(screen.queryByRole('button', { name: /in 3D/ })).toBeNull();
});

it('QA-1 (#430) a multi-drawing answer opens on the most useful reference: a page, a non-zero value, the highest level', () => {
  const zero = { ...flatA, answer: { ...flatA.answer, answer: 0, level: answerHigh.level } };
  const some = { ...flatB, answer: { ...flatB.answer, answer: 36, level: answerMedium.level } };
  show({ ...projectAsk, parts: [zero, some] });
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  expect(rows()[0]?.textContent).toContain(`${LB}: 36`);
  cleanup();
  // two non-zero values with a page: the higher level wins
  const low = { ...flatA, answer: { ...flatA.answer, level: answerMedium.level } };
  const high = { ...flatB, answer: { ...flatB.answer, level: answerHigh.level } };
  show({ ...projectAsk, parts: [low, high] });
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  cleanup();
  // a building model (no page) is never opened first, whatever its value
  const model = {
    ...flatB,
    answer: { ...flatB.answer, pages: [], answer: 77, level: answerHigh.level },
  };
  show({ ...projectAsk, parts: [flatA, model] });
  expect(figure().getAttribute('aria-label')).toBe('Reference 1 of 2');
});

it('QA-2 (#430) the card says what the number counts: the quantity label and its rule', () => {
  show();
  const q = flatA.answer.quantity as NonNullable<typeof flatA.answer.quantity>;
  const line = (rows()[0] as HTMLElement).querySelector('.en-counts');
  expect(line?.textContent).toBe(
    `${q.label.charAt(0).toUpperCase()}${q.label.slice(1)}: ${q.rule.text}.`,
  );
});

it('QA-3 (#430) the picked reference survives a remount (the layout switch at the phone width)', () => {
  const ask = { ...projectAsk };
  const view = render(
    <ChatAnswer ask={ask} project={projectWith(null)} projectId={project.id} pack={null} />,
  );
  fireEvent.click(within(refs()[1] as HTMLElement).getByRole('button'));
  view.unmount();
  render(<ChatAnswer ask={ask} project={projectWith(null)} projectId={project.id} pack={null} />);
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
});

it('QA-5 (#430) a count without a noun takes its quantity label: "2 apartments", "1 apartment"', () => {
  const q = flatA.answer.quantity as NonNullable<typeof flatA.answer.quantity>;
  const count = (n: number) => ({
    ...flatA,
    answer: {
      ...flatA.answer,
      answer: n,
      unit: 'count' as const,
      quantity: { ...q, noun: null, label: 'apartment', measure: 'count' as const },
    },
  });
  show({ ...projectAsk, parts: [count(2)] });
  expect(rows()[0]?.textContent).toContain(`${LA}: 2 apartments`);
  cleanup();
  show({ ...projectAsk, parts: [count(1)] });
  expect(rows()[0]?.textContent).toContain(`${LA}: 1 apartment`);
  expect(rows()[0]?.textContent).not.toContain('1 apartments');
});

it('QA-6 (#430) onReference gets the shown drawing on open and on every switch', () => {
  const onReference = vi.fn();
  render(
    <ChatAnswer
      ask={{ ...projectAsk }}
      project={projectWith(null)}
      projectId={project.id}
      pack={null}
      onReference={onReference}
    />,
  );
  expect(onReference.mock.calls).toEqual([[flatA.drawing_id]]);
  fireEvent.click(within(refs()[1] as HTMLElement).getByRole('button'));
  expect(onReference.mock.calls).toEqual([[flatA.drawing_id], [flatB.drawing_id]]);
});
