import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { error, project } from '../api/fixtures';
import { mockApi, reply } from '../test/mockApi';
import { AboutScreen } from './AboutScreen';

const PID = project.id;
afterEach(cleanup);

describe('AboutScreen', () => {
  it('SH-80 with a project: one request; each drawing by its plain name and file, with its credit', async () => {
    const [first, second, ...rest] = project.drawings;
    if (!first || !second) throw new Error('project.json needs two drawings');
    const drawings = [
      { ...first, credit: 'Credit: Example Org, CC BY 4.0' },
      { ...second, credit: null },
      ...rest,
    ];
    const api = mockApi({ [`GET /api/projects/${PID}`]: { ...project, drawings } });
    render(<AboutScreen projectId={PID} />);
    expect(screen.getByRole('heading', { level: 1, name: 'About Vellum' })).toBeTruthy();
    expect(await screen.findByText('Example Org, CC BY 4.0')).toBeTruthy();
    expect(screen.getByText(project.name)).toBeTruthy();
    for (const d of drawings) {
      expect(screen.getByText(d.name)).toBeTruthy();
      expect(screen.getByText(d.file)).toBeTruthy();
    }
    expect(screen.getByText('No credit recorded for this file')).toBeTruthy();
    expect(screen.queryByText(/Credit:/)).toBeNull();
    expect(api.calls).toHaveLength(1);
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
