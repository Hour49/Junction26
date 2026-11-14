import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, error, project } from '../api/fixtures';
import { mockApi, reply } from '../test/mockApi';
import { AboutScreen } from './AboutScreen';

const PID = project.id;
const [first, second] = project.drawings;
afterEach(cleanup);

describe('AboutScreen', () => {
  it('SH-80 with a project: each drawing with its credit, "Credit:" stripped once, null said in words', async () => {
    const routes: Record<string, unknown> = { [`GET /api/projects/${PID}`]: project };
    for (const d of project.drawings) {
      const credit =
        d.drawing_id === first?.drawing_id
          ? 'Credit: Example Org, CC BY 4.0'
          : d.drawing_id === second?.drawing_id
            ? null
            : drawing.credit;
      routes[`GET /api/drawings/${d.drawing_id}`] = { ...drawing, id: d.drawing_id, credit };
    }
    const api = mockApi(routes);
    render(<AboutScreen projectId={PID} />);
    expect(screen.getByRole('heading', { level: 1, name: 'About Vellum' })).toBeTruthy();
    expect(await screen.findByText('Example Org, CC BY 4.0')).toBeTruthy();
    expect(screen.getByText(project.name, { exact: false })).toBeTruthy();
    for (const d of project.drawings) expect(screen.getByText(d.file)).toBeTruthy();
    expect(screen.getByText('No credit recorded for this file')).toBeTruthy();
    expect(screen.queryByText(/Credit:/)).toBeNull();
    expect(api.calls).toHaveLength(1 + project.drawings.length);
    expect(api.calls.slice(1).every((c) => c.url.endsWith(`?project=${PID}`))).toBe(true);
  });

  it('SH-80 without a project: the hint and no request', () => {
    const api = mockApi({});
    render(<AboutScreen projectId={null} />);
    expect(screen.getByText("Open a project to see its drawings' credits.")).toBeTruthy();
    expect(api.calls).toHaveLength(0);
  });

  it('SH-80 a 500 shows the error with Retry, which asks again', async () => {
    let n = 0;
    const api = mockApi({
      [`GET /api/projects/${PID}`]: () =>
        n++ === 0 ? reply(500, error) : { ...project, drawings: [] },
    });
    render(<AboutScreen projectId={PID} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('This project has no drawings.')).toBeTruthy();
    expect(api.calls).toHaveLength(2);
  });
});
