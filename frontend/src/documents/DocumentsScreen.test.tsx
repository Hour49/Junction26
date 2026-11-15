import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { project, projectRunning, projectTriaged } from '../api/fixtures';
import type { ProjectView } from '../api';
import { mockApi } from '../test/mockApi';
import { flush, must } from '../ingest/testing';
import { DocumentsScreen } from './DocumentsScreen';

const PID = project.id;

function show(body: ProjectView = project, pack: string | null = null) {
  const api = mockApi({ [`GET /api/projects/${body.id}`]: body });
  render(<DocumentsScreen projectId={body.id} pack={pack} />);
  return api;
}

afterEach(cleanup);

describe('DocumentsScreen (documents.md)', () => {
  it('DOC-1 and DOC-16: kicker and title, no counts line; the rules link lives in the country picker', async () => {
    show(project, 'fi');
    await flush();
    expect(screen.getByRole('heading', { level: 1, name: 'Documents' })).toBeTruthy();
    expect(document.body.textContent).toContain(project.name);
    expect(document.body.textContent).not.toContain('files ingested');
    expect(screen.queryByRole('link', { name: 'Building-code checks' })).toBeNull();
  });

  it('DOC-2 while running: the drawings list waits, no issues request', async () => {
    const api = show({ ...projectRunning, id: PID });
    await flush();
    expect(api.calls.some((c) => c.url.includes('/issues'))).toBe(false);
    expect(screen.getByRole('region', { name: 'Drawings' })).toBeTruthy();
  });

  it('P6a P7 no Files region, no Issues on demand, no issues request', async () => {
    const api = show();
    await flush();
    expect(screen.queryByRole('region', { name: 'Files' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Issues on demand' })).toBeNull();
    expect(document.body.textContent).not.toContain('Issues on demand');
    expect(document.body.textContent).not.toContain('Nothing needs your answer');
    expect(document.body.textContent).not.toContain('not a floor plan');
    expect(api.calls.some((c) => c.url.includes('/issues'))).toBe(false);
  });

  it('DOC-10 a drawing card: names, route word, its file’s state label and Open on the right', async () => {
    show();
    await flush();
    const drawings = within(screen.getByRole('region', { name: 'Drawings' }));
    const d = must(project.drawings[0]);
    const card = must(drawings.getByText('Drawn plan 1').closest('li'));
    expect(card.querySelector('b')?.textContent).toBe('Drawn plan 1'); // the plain name is the title (#224)
    expect(within(card).getByText(d.file)).toBeTruthy(); // the path stays as the small line
    const open = within(card).getByRole('link', { name: 'Open' });
    expect(open.getAttribute('href')).toBe(`#/p/${PID}/d/${d.drawing_id}/engineer`);
    // the file's state (flat-a.pdf is ready) as in Files before, linking to the file's trace
    const file = must(project.files.find((f) => f.path === d.file));
    expect(file.state).toBe('ready');
    const state = within(card).getByRole('link', { name: `How ${d.file} was read` });
    expect(state.getAttribute('href')).toBe(`#/p/${PID}/f/${file.id}`);
    expect(state.textContent).toContain('ready');
    // Open is the card's right-hand part: a sibling after the left column that holds the state label
    const left = must(state.parentElement);
    expect(left.nextElementSibling?.contains(open)).toBe(true);
    expect(left.contains(open)).toBe(false);
  });

  it('DOC-10 a flagged file’s drawing shows flagged', async () => {
    show();
    await flush();
    const drawings = within(screen.getByRole('region', { name: 'Drawings' }));
    const d = must(project.drawings.find((x) => x.file === 'plans/flat-b.pdf'));
    const card = must(drawings.getByText(d.file).closest('li'));
    expect(within(card).getByText('flagged')).toBeTruthy();
  });

  it('P7 Set aside: only the files that are not drawings, each with its reason and a state link to its trace', async () => {
    const body = { ...projectTriaged, id: PID };
    show(body);
    await flush();
    const region = within(screen.getByRole('region', { name: 'Set aside' }));
    const rows = region.getAllByRole('listitem');
    const asideFiles = body.files.filter((f) => f.state === 'set_aside');
    expect(rows).toHaveLength(asideFiles.length);
    const site = must(body.files.find((f) => f.path === 'photos/site.jpg'));
    const row = must(region.getByText(site.path).closest('li'));
    expect(row.textContent).toContain('Not a floor plan: not a drawing');
    expect(row.textContent).not.toContain('(1600'); // no technical parenthetical
    const link = within(row).getByRole('link', { name: `How ${site.path} was read` });
    expect(link.getAttribute('href')).toBe(`#/p/${PID}/f/${site.id}`);
    expect(link.textContent).toContain('set aside');
    // a drawing's file is not repeated here
    expect(region.queryByText('plans/flat-a.pdf')).toBeNull();
  });

  it('P7 Set aside is absent when every file is a drawing or read', async () => {
    show();
    await flush();
    expect(screen.queryByRole('region', { name: 'Set aside' })).toBeNull();
    expect(screen.queryByText('Set aside')).toBeNull();
  });
});
