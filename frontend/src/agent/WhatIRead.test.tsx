// chat-ux #8: the empty agent chat says what was read from each drawing, from the project's own data (no model call).
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { ProjectView } from '../api';
import { project } from '../api/fixtures';
import { readLine, WhatIRead } from './WhatIRead';

afterEach(cleanup);

const items = () =>
  within(screen.getByRole('region', { name: 'What I read' })).getAllByRole('listitem');

it("each askable drawing: its name, kind and route, the takeoff's rooms, doors and windows, the read sentence", () => {
  render(<WhatIRead project={project} />);
  const [a, b] = items() as [HTMLElement, HTMLElement];
  expect(within(a).getByText('Drawn plan 1').tagName).toBe('B');
  expect(a.textContent).toContain('PDF vector · ');
  expect(a.textContent).toContain('5 rooms (52.27 m² indoors) · 2 doors · 2 windows');
  expect(a.textContent).toContain(
    'Read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet.',
  );
  // a flagged drawing says why, in the server's words
  expect(b.textContent).toContain('1 conflict between the two methods (room areas)');
});

it('at most 3 drawings, then how many more', () => {
  render(<WhatIRead project={project} />);
  expect(items()).toHaveLength(3); // project.json has 5 askable drawings
  expect(screen.getByText('and 2 more drawings')).toBeTruthy();
});

it('nothing for a project with no askable drawing', () => {
  const none: ProjectView = {
    ...project,
    drawings: project.drawings.map((d) => ({ ...d, state: 'set_aside' as const })),
  };
  const { container } = render(<WhatIRead project={none} />);
  expect(container.textContent).toBe('');
});

it('readLine: singulars, no zero counts, no area without rooms; nothing from an empty takeoff', () => {
  expect(readLine({ room: 1, door: 0, window: 1 })).toBe('1 room · 1 window');
  expect(readLine({ door: 3, 'area:room|indoor': 10 })).toBe('3 doors');
  expect(readLine({})).toBeNull();
  expect(readLine(undefined)).toBeNull();
});
