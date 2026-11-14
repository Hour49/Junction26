// docs/ui-tooltips.md P1 rows of the ingest screens: each tip shows its words on hover or keyboard focus.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { project, trace } from '../api/fixtures';
import { INGEST_TIPS, STAGE_TIPS, STATE_TIPS } from '../shell/tips-ingest';
import { mockApi } from '../test/mockApi';
import { stubResizeObserver } from '../test/resizeObserver';
import { FileTraceScreen } from './FileTraceScreen';
import { HomeScreen } from './HomeScreen';
import { STAGE_LABEL } from './ingest';
import { ProgressCard } from './ProgressCard';
import { StateBadge } from './ProjectScreen';
import { flush } from './testing';

beforeEach(stubResizeObserver);
afterEach(cleanup);

/** The tip's words, once a mouse moves over the trigger. */
async function hover(el: Element, text: string) {
  fireEvent.pointerMove(el, { pointerType: 'mouse' });
  expect(within(await screen.findByRole('tooltip')).getByText(text)).toBeTruthy();
}
/** The same words on keyboard focus of the trigger (or its focusable wrapper). */
async function focus(el: HTMLElement, text: string) {
  (el.closest<HTMLElement>('[tabindex="0"]') ?? el).focus();
  expect(within(await screen.findByRole('tooltip')).getByText(text)).toBeTruthy();
}

describe('ingest tips (P1)', () => {
  it('"Try the sample project" explains the sample', async () => {
    mockApi({});
    render(<HomeScreen />);
    await hover(screen.getByRole('button', { name: 'Try the sample project' }), INGEST_TIPS.sample);
  });

  it('"Drawings ready" and "Set aside" explain their numbers', async () => {
    render(<ProgressCard project={project} now={Date.now()} />);
    await focus(screen.getByText('Drawings ready'), INGEST_TIPS.drawingsReady);
    cleanup();
    render(<ProgressCard project={project} now={Date.now()} />);
    await hover(screen.getByText('Set aside'), INGEST_TIPS.setAside);
  });

  it.each(['ready', 'flagged', 'text_only', 'set_aside'] as const)(
    'the file state word "%s" explains itself',
    async (state) => {
      const { container } = render(<StateBadge state={state} />);
      await focus(container.firstElementChild as HTMLElement, STATE_TIPS[state]);
    },
  );

  it('"How it was read" and each stage name explain the trace', async () => {
    const PID = trace.project_id;
    mockApi({ [`GET /api/projects/${PID}/files/${trace.file.id}/trace`]: trace });
    render(<FileTraceScreen projectId={PID} fileId={trace.file.id} />);
    await flush();
    await hover(screen.getByText(/^How it was read/), INGEST_TIPS.stages);
    cleanup();
    mockApi({ [`GET /api/projects/${PID}/files/${trace.file.id}/trace`]: trace });
    render(<FileTraceScreen projectId={PID} fileId={trace.file.id} />);
    await flush();
    const first = trace.stages[0];
    if (!first) throw new Error('fixture has no stage');
    await focus(
      screen.getAllByText(STAGE_LABEL[first.stage])[0] as HTMLElement,
      STAGE_TIPS[first.stage],
    );
  });
});
