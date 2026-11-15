import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DocumentsScreen } from '../documents/DocumentsScreen';
import { drawing, info, project, projectIssues, projectList } from '../api/fixtures';
import { mockApi } from '../test/mockApi';
import { stubResizeObserver } from '../test/resizeObserver';
import { Header } from './Header';
import { InfoBar } from './InfoBar';
import { InfoProvider } from './info';
import { parseRoute } from './route';
import { TIPS, fileStateTip } from './tips';

beforeEach(stubResizeObserver);
afterEach(cleanup);

const PID = project.id;
const shown = async (text: string) => {
  // Radix renders the words twice (the box and a hidden role=tooltip copy for screen readers).
  expect((await screen.findAllByText(text)).length).toBeGreaterThan(0);
  expect(screen.getAllByRole('tooltip').length).toBeGreaterThan(0);
};
const projectRoutes = {
  'GET /api/info': info,
  'GET /api/projects': projectList,
  [`GET /api/projects/${PID}`]: project,
  [`GET /api/projects/${PID}/issues`]: projectIssues,
  ...Object.fromEntries(
    projectIssues.issues
      .filter((i) => i.drawing_id)
      .map((i) => [`GET /api/drawings/${String(i.drawing_id)}`, drawing]),
  ),
};

describe('tips applied in the shell, documents and export (docs/ui-tooltips.md, P1)', () => {
  it('the offline badge explains itself on focus', async () => {
    mockApi({ 'GET /api/info': { ...info, no_keys: true } });
    render(
      <InfoProvider>
        <InfoBar />
      </InfoProvider>,
    );
    const badge = await screen.findByText(/offline/i);
    (badge.closest('[tabindex]') as HTMLElement).focus();
    await shown(TIPS.offline);
  });

  it('the header tabs and the country pill explain themselves on focus', async () => {
    mockApi(projectRoutes);
    render(
      <InfoProvider>
        <Header route={parseRoute(`#/p/${PID}/documents`)} />
      </InfoProvider>,
    );
    screen.getByRole('link', { name: /^Documents/ }).focus();
    await shown(TIPS.tabDocuments);
    screen.getByRole('link', { name: 'Chat' }).focus();
    await shown(TIPS.tabChat);
    const country = await screen.findByRole('button', { name: /^Country rules/ });
    country.focus();
    await shown(TIPS.country);
  });

  it('the export button explains itself on hover', async () => {
    mockApi(projectRoutes);
    render(<Header route={parseRoute(`#/p/${PID}/documents`)} />);
    const button = screen.getByRole('button', { name: 'Export scan as CSV' });
    fireEvent.pointerMove(button, { pointerType: 'mouse' });
    await shown(TIPS.export);
  });

  it('each drawing card’s file state word explains itself', async () => {
    mockApi(projectRoutes);
    render(<DocumentsScreen projectId={PID} pack={null} />);
    const flagged = await screen.findAllByText('flagged');
    (flagged[0]?.closest('[tabindex]') as HTMLElement).focus();
    await shown(fileStateTip('flagged'));
  });

  it('a state without a tip text shows no tip', () => {
    expect(fileStateTip('nonsense')).toBe('');
  });
});
