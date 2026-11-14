// chat.md "Demo parity": the chat's answer card (CH-30..CH-35), PageViewer mocked to read what it gets.
import type { ComponentProps } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ProjectAnswer, ProjectView } from '../api';
import { project, projectAsk } from '../api/fixtures';
import { routeLabel } from '../ingest/ingest';
import type { PageViewer } from '../viewer/PageViewer';
import { ChatAnswer } from './ChatAnswer';
import { kindName } from './format';

type ViewerProps = ComponentProps<typeof PageViewer>;
const viewers: ViewerProps[] = [];
vi.mock('../viewer/PageViewer', () => ({
  PageViewer: (props: ViewerProps) => {
    viewers.push(props);
    return <div data-testid="viewer">{props.file}</div>;
  },
}));

type Part = ProjectAnswer['parts'][number];
const [flatA, flatB] = projectAsk.parts as [Part, Part, Part];

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
  render(<ChatAnswer ask={ask} project={proj} projectId={project.id} pack={null} />);
}
const refs = () =>
  within(screen.getByRole('list', { name: 'References' })).getAllByRole('listitem');
const rows = () =>
  within(screen.getByRole('list', { name: 'Per drawing' })).getAllByRole('listitem');
const figure = () => screen.getByRole('figure', { name: /^Reference / });

afterEach(() => {
  cleanup();
  viewers.length = 0;
});

it('CH-30 a sheet that is not a floor plan comes first, in the rows and the references alike', () => {
  show(projectAsk, projectWith('other_drawing'));
  expect(rows()[0]?.textContent).toContain(flatB.name);
  expect(refs()[0]?.textContent).toContain(flatB.name);
  expect(rows()[1]?.textContent).toContain(flatA.name);
  cleanup();
  show(projectAsk, projectWith(null));
  expect(rows()[0]?.textContent).toContain(flatA.name);
  expect(refs()[0]?.textContent).toContain(flatA.name);
});

it('CH-31 the lead: the note alone without a total; a total in bold with its note', () => {
  show();
  expect(screen.getByText(projectAsk.total_note)).toBeTruthy();
  expect(screen.queryByTestId('answer-value')).toBeNull();
  cleanup();
  show({ ...projectAsk, total: 4, total_unit: 'count', total_note: 'Two floors.' });
  const value = screen.getByTestId('answer-value');
  expect(value.textContent).toBe('4');
  expect(value.closest('strong, .en-lead')).toBeTruthy();
  expect(screen.getByText('Two floors.')).toBeTruthy();
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

it('CH-33 the arrows go through the references with a page and wrap; one reference has none', () => {
  show();
  fireEvent.click(screen.getByRole('button', { name: 'Next reference' }));
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  expect(viewers.at(-1)?.file).toBe(flatB.name);
  fireEvent.click(screen.getByRole('button', { name: 'Next reference' }));
  expect(figure().getAttribute('aria-label')).toBe('Reference 1 of 2');
  fireEvent.click(screen.getByRole('button', { name: 'Previous reference' }));
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  cleanup();
  show({ ...projectAsk, parts: [flatA] });
  expect(screen.queryByRole('button', { name: /reference$/ })).toBeNull();
});

it('CH-34 the references: numbered buttons, kind and route in words, the current one pressed', () => {
  show(projectAsk, projectWith(null));
  const [one, two] = refs() as [HTMLElement, HTMLElement];
  const b1 = within(one).getByRole('button');
  const b2 = within(two).getByRole('button');
  expect(b1.textContent).toContain('1');
  expect(b1.textContent).toContain(flatA.name);
  expect(b1.textContent).toContain(`${kindName('pdf_vector')} · ${routeLabel('vector')}`);
  expect(b2.textContent).toContain(`${kindName('png_plan')} · ${routeLabel('raster')}`);
  expect(b1.getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(b2);
  expect(b2.getAttribute('aria-pressed')).toBe('true');
  expect(figure().getAttribute('aria-label')).toBe('Reference 2 of 2');
  cleanup();
  // a building model has no page: plain text, "no preview", skipped by the arrows
  show({ ...projectAsk, parts: [flatA, { ...flatB, answer: { ...flatB.answer, pages: [] } }] });
  const model = refs()[1] as HTMLElement;
  expect(within(model).queryByRole('button')).toBeNull();
  expect(model.textContent).toContain('no preview');
  expect(figure().getAttribute('aria-label')).toBe('Reference 1 of 1');
});

it('CH-35 one row per answering drawing with its value, status and Show it on; nothing for a refused one', () => {
  show();
  expect(rows()).toHaveLength(2);
  const [a] = rows() as [HTMLElement];
  expect(a.textContent).toContain(`${flatA.name}: 2`);
  expect(a.textContent).toContain('One method');
  expect(within(a).getByRole('link', { name: `Show it on ${flatA.name}` })).toBeTruthy();
  const refused = projectAsk.parts[2]?.name ?? '';
  expect(document.body.textContent).not.toContain(refused);
});
