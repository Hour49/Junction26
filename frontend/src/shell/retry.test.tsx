// QA board #430: a backend blip (502) left the chat on "Something went wrong" with no way back. Each screen's
// first-load error now offers Retry, which asks again; a 502/503/504/network error is said plainly.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, info, project } from '../api/fixtures';
import { AgentChat } from '../agent/AgentChat';
import { ChecksScreen } from '../checks/ChecksScreen';
import { EngineerPage } from '../engineer/EngineerPage';
import { ProjectChat } from '../engineer/ProjectChat';
import { flush } from '../ingest/testing';
import { mockApi, never, reply } from '../test/mockApi';
import { stubResizeObserver } from '../test/resizeObserver';
import { InfoProvider } from './info';
import { SERVER_DOWN } from './ErrorView';

afterEach(cleanup);

const PID = project.id;
const D = project.drawings[0]?.drawing_id ?? '';
const proxy502 = reply(502, '<html>Bad Gateway</html>');

/** The screen's own GET answers 502 until Retry is clicked, then the fixture; everything else answers normally. */
const server = { down: true };
function routes(first: string, body: unknown) {
  server.down = true;
  const all: Record<string, unknown> = {
    'GET /api/info': info,
    [`GET /api/projects/${PID}`]: project,
    [`GET /api/projects/${PID}/checks`]: never(),
    [`GET /api/projects/${PID}/issues`]: never(),
    [`GET /api/projects/${PID}/review`]: never(),
  };
  for (const d of project.drawings)
    all[`GET /api/drawings/${d.drawing_id}`] = { ...drawing, id: d.drawing_id };
  all[first] = () => {
    return server.down ? proxy502 : body;
  };
  return all;
}

const cases: [string, string, unknown, () => ReactElement][] = [
  ['AgentChat', `GET /api/projects/${PID}`, project, () => <AgentChat projectId={PID} />],
  ['ProjectChat', `GET /api/projects/${PID}`, project, () => <ProjectChat projectId={PID} />],
  [
    'EngineerPage',
    `GET /api/drawings/${D}`,
    { ...drawing, id: D },
    () => <EngineerPage projectId={PID} drawingId={D} />,
  ],
  [
    'ChecksScreen',
    `GET /api/projects/${PID}`,
    project,
    () => <ChecksScreen projectId={PID} pack="fi" />,
  ],
];

describe('Retry after a backend blip', () => {
  it.each(cases)(
    '%s: a 502 says it plainly, and Retry loads the screen',
    async (_, path, __, ui) => {
      stubResizeObserver();
      const api = mockApi(routes(path, __));
      const asked = () => api.calls.filter((c) => path.endsWith(c.url.split('?')[0] ?? '')).length;
      render(<InfoProvider>{ui()}</InfoProvider>);
      const alert = await screen.findByRole('alert');
      expect(alert.textContent).toContain(SERVER_DOWN);
      expect(alert.textContent).not.toContain('the server answered 502');
      expect(alert.textContent).toContain('code: http-502');
      const before = asked();
      server.down = false;
      fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
      await flush();
      await flush();
      expect(screen.queryByText(SERVER_DOWN)).toBeNull();
      expect(asked()).toBe(before + 1);
    },
  );
});
