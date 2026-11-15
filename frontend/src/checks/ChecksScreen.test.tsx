import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it } from 'vitest';
import { drawing, info, project, projectRunning } from '../api/fixtures';
import type { ProjectView } from '../api';
import { flush, must } from '../ingest/testing';
import { InfoProvider } from '../shell/info';
import { mockApi, never, reply } from '../test/mockApi';
import { ChecksScreen } from './ChecksScreen';
import bogdanChecks from '@fixtures/project_checks.json';
import bogdanInfo from '@fixtures/info.json';
import {
  checks,
  D1,
  D2,
  drawingChecks,
  FAIL_MEANS,
  NOTE,
  pack,
  result,
  ruleCheck,
} from './testing';
import type { ProjectChecks } from './types';

const PID = project.id;
const CHECKS = `GET /api/projects/${PID}/checks`;

function routes(over: Record<string, unknown> = {}) {
  return {
    'GET /api/info': { ...info, rule_packs: [pack] },
    [`GET /api/projects/${PID}`]: project,
    [CHECKS]: checks,
    [`GET /api/drawings/${D1}`]: { ...drawing, id: D1 },
    [`GET /api/drawings/${D2}`]: { ...drawing, id: D2 },
    ...over,
  };
}

async function show(packId: string | null = 'fi', over: Record<string, unknown> = {}) {
  const api = mockApi(routes(over));
  const view = render(
    <InfoProvider>
      <ChecksScreen projectId={PID} pack={packId} />
    </InfoProvider>,
  );
  await flush();
  return { api, view };
}

const checkCalls = (api: { calls: { url: string }[] }) =>
  api.calls.filter((c) => c.url.includes('/checks'));
const cards = () => screen.getAllByRole('article');
const fileOf = (did: string) => must(project.files.find((f) => f.drawing_id === did)).path;

afterEach(cleanup);

describe('ChecksScreen', () => {
  it('CK-1 without a pack nothing is requested and the screen says to choose a country', async () => {
    const { api } = await show(null);
    expect(api.calls.filter((c) => !c.url.endsWith('/api/info'))).toEqual([]);
    expect(screen.getByText('Choose a country in the header to run its pre-check.')).toBeTruthy();
  });

  it('CK-2 the heading names the pack; no law line, pack note or summary line above the rules', async () => {
    await show();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(`Pre-check: ${pack.name}`);
    expect(screen.queryByRole('note')).toBeNull();
    expect(document.body.textContent).not.toContain(NOTE);
    expect(document.body.textContent).not.toContain(`${pack.country_name} · ${pack.law}`);
    expect(screen.queryByText(FAIL_MEANS)).toBeNull();
    expect(screen.queryByText(/rules? failed, .* over /)).toBeNull();
  });

  it('CK-4 the table counts places per rule', async () => {
    const { api } = await show();
    expect(checkCalls(api).map((c) => c.url)).toEqual([`/api/projects/${PID}/checks?pack=fi`]);
    const table = screen.getByRole('table', { name: /rules/i });
    const r2 = within(table).getByRole('row', { name: /Rule R2/ });
    expect(within(r2).getByRole('rowheader').textContent).toContain('Rule R2');
    expect(
      within(r2)
        .getAllByRole('cell')
        .map((c) => c.textContent),
    ).toEqual(['1', '1', '0']);
    expect(within(table).getByRole('row', { name: /Rule R4/ }).textContent).toContain(
      'Does not apply to these drawings',
    );
  });

  it('CK-5/6/7/8 failed then cannot tell; the cannot-tell look is its own; file and why shown, no clause', async () => {
    await show();
    const list = cards();
    expect(list).toHaveLength(2); // D1: d cannot tell; D2: f fails (passes are counted, not listed)
    const [d1, d2] = [must(list[0]), must(list[1])];
    expect(d1.textContent).toContain('? Cannot tell');
    expect(d1.className).toContain('ck-cannot_tell');
    expect(d1.className).not.toMatch(/ck-(fail|pass)\b/);
    expect(d1.textContent).not.toMatch(/Fails|Passes/);
    expect(d1.textContent).toContain('not measured');
    expect(d2.textContent).toContain('✕ Fails');
    expect(d2.textContent).toContain('0.75 m measured, limit at least 0.80 m');
    expect(d2.textContent).toContain('Why f.');
    expect(d2.textContent).toContain(`File: ${fileOf(D2)}`);
    expect(d1.textContent).toContain(`File: ${fileOf(D1)}`);
    expect(d2.textContent).not.toContain('Decree 1/2000 § 2');
    expect(d2.querySelector('blockquote')).toBeNull();
    expect(within(d2).queryByRole('link')).toBeNull();
  });

  it('CK-5 a drawing with only passes is folded into one line', async () => {
    const allPass: ProjectChecks = {
      ...checks,
      drawings: checks.drawings.map((d) => ({
        ...d,
        rules: d.rules.map((r) => ({
          ...r,
          results: r.results.map((x) => ({ ...x, status: 'pass' as const })),
        })),
      })),
    };
    await show('fi', { [CHECKS]: allPass });
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(screen.getByText('2 drawings pass every checked place')).toBeTruthy();
    expect(screen.getByText('Every checked place passes these rules.')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Findings in your files' })).toBeNull();
  });

  it('not_applicable: a drawing no rule applies to is its own line, never folded into "passes"', async () => {
    const none: ProjectChecks = {
      ...checks,
      drawings: [
        drawingChecks(D1, [ruleCheck('R4', 4, [])]),
        drawingChecks(D2, [ruleCheck('R1', 1, [result('e', 'R1', 'pass')])]),
      ],
    };
    await show('fi', { [CHECKS]: none });
    expect(screen.getByText('1 drawing passes every checked place')).toBeTruthy();
    expect(screen.getByText('1 drawing has nothing these rules apply to')).toBeTruthy();
    expect(screen.getByRole('row', { name: /Rule R4/ }).textContent).toContain(
      'Does not apply to these drawings',
    );
  });

  it('a rule that cannot tell on a drawing without any result gets a "Cannot tell" card with its why', async () => {
    const blind: ProjectChecks = {
      ...checks,
      drawings: [
        drawingChecks(D1, [
          {
            ...ruleCheck('R1', 1, []),
            status: 'cannot_tell',
            why: 'No doors were read on this drawing.',
          },
        ]),
      ],
    };
    await show('fi', { [CHECKS]: blind });
    const card = must(cards()[0]);
    expect(card.textContent).toContain('? Cannot tell');
    expect(card.textContent).toContain('No doors were read on this drawing.');
    expect(card.textContent).not.toContain('Decree 1/2000 § 1');
    expect(card.textContent).toContain('Not located on the drawing');
    expect(card.textContent).not.toContain('measured');
    expect(screen.queryByText(/nothing these rules apply to/)).toBeNull();
    expect(screen.getByRole('row', { name: /Rule R1/ }).textContent).not.toContain(
      'Does not apply',
    );
    expect(screen.getByRole('row', { name: /Rule R1/ }).textContent).toContain(
      'Cannot tell on 1 drawing: nothing could be read',
    );
  });

  it("Bogdan's fixtures (project_checks.json, info.json rule_packs) render: heading, fail card, file from the payload", async () => {
    const fi = must(bogdanInfo.rule_packs.find((p) => p.id === 'fi'));
    await show('fi', { 'GET /api/info': bogdanInfo, [CHECKS]: bogdanChecks });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(`Pre-check: ${fi.name}`);
    expect(screen.queryByRole('note')).toBeNull();
    const d = must(bogdanChecks.drawings[0]);
    const card = must(cards()[0]);
    expect(card.textContent).toContain(`File: ${d.file}`); // not in this project's files: the payload's
    expect(card.textContent).toContain('✕ Fails');
    expect(card.textContent).toContain('6.03 m² measured');
  });

  it('CK-5 one all-pass drawing reads "1 drawing passes every checked place"', async () => {
    const d1 = must(checks.drawings[0]);
    const one: ProjectChecks = {
      ...checks,
      drawings: [
        { ...d1, rules: [{ ...must(d1.rules[0]), results: [result('a', 'R1', 'pass')] }] },
        ...checks.drawings.slice(1),
      ],
    };
    await show('fi', { [CHECKS]: one });
    expect(screen.getByText('1 drawing passes every checked place')).toBeTruthy();
  });

  it('"Show on the drawing" opens the drawing in a pop-up; Close shuts it', async () => {
    await show();
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(within(must(cards()[1])).getByRole('button', { name: /Show on the drawing/ }));
    await flush();
    const dialog = screen.getByRole('dialog', { name: fileOf(D2) });
    expect(
      within(dialog).getByRole('button', { name: 'Mark 1: Door f, fails the rule' }),
    ).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    await flush();
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it("CK-9 the card's file is this project's file path, never the payload's", async () => {
    const p: ProjectView = {
      ...project,
      files: project.files.map((f) => (f.drawing_id === D2 ? { ...f, path: 'mine/plan.pdf' } : f)),
    };
    const shared = {
      ...checks,
      drawings: checks.drawings.map((d) => ({ ...d, file: 'someone-else/plan.pdf' })),
    };
    await show('fi', { [`GET /api/projects/${PID}`]: p, [CHECKS]: shared });
    expect(document.body.textContent).toContain('File: mine/plan.pdf');
    expect(document.body.textContent).not.toContain('someone-else');
  });

  it('CK-10 payload strings render as text', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    const d2 = must(checks.drawings[1]);
    const bad = {
      ...checks,
      drawings: [
        {
          ...d2,
          rules: [
            {
              ...must(d2.rules[1]),
              title: evil,
              results: [{ ...result('f', 'R2', 'fail'), why: evil }],
            },
          ],
        },
      ],
    };
    await show('fi', { [CHECKS]: bad });
    expect(document.body.textContent).toContain(evil);
    expect(document.querySelector('img[src="x"]')).toBeNull();
  });

  it('CK-11 "Show on the drawing" loads the pages once and draws the result toned; no marks: "Not located"', async () => {
    const { api } = await show();
    const open = async () => {
      fireEvent.click(
        within(must(cards()[1])).getByRole('button', { name: /Show on the drawing/ }),
      );
      await flush();
    };
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await flush();
    await open();
    expect(
      api.calls.filter(
        (c) => c.url.startsWith(`/api/drawings/${D2}`) && !c.url.includes('/pages/'),
      ),
    ).toHaveLength(1);
    const badge = screen.getByRole('button', { name: 'Mark 1: Door f, fails the rule' });
    expect(badge.className).toContain('vw-badge--fail');
    cleanup();
    const d2c = must(checks.drawings[1]);
    const unplaced = {
      ...checks,
      drawings: [
        {
          ...d2c,
          rules: [
            { ...must(d2c.rules[1]), results: [{ ...result('f', 'R2', 'fail'), marks: [] }] },
          ],
        },
      ],
    };
    await show('fi', { [CHECKS]: unplaced });
    expect(screen.getByText('Not located on the drawing')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Show on the drawing/ })).toBeNull();
  });

  it('CK-12 one "Findings in your files" section; no surveyor or export links', async () => {
    await show();
    expect(screen.getByRole('heading', { level: 2, name: 'Findings in your files' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Open in the surveyor/ })).toBeNull();
    expect(screen.queryByRole('link', { name: /Export issues and plans/ })).toBeNull();
  });

  it('CK-13 a running project asks no checks; a 409 reads the same', async () => {
    const running = await show('fi', { [`GET /api/projects/${PID}`]: projectRunning });
    expect(checkCalls(running.api)).toHaveLength(0);
    expect(screen.getByText('The pre-check runs once the drawings are read.')).toBeTruthy();
    cleanup();
    await show('fi', { [CHECKS]: reply(409, { detail: 'not yet', code: 'not_done' }) });
    expect(screen.getByText('The pre-check runs once the drawings are read.')).toBeTruthy();
  });

  it('CK-14 404 unknown-pack: rules not available; another 404 code: the error view', async () => {
    await show('xx', { [CHECKS]: reply(404, { detail: 'no pack xx', code: 'unknown-pack' }) });
    expect(
      screen.getByText('These rules are not available. Pick another country in the header.'),
    ).toBeTruthy();
    cleanup();
    await show('fi', { [CHECKS]: reply(404, { detail: 'no such project', code: 'not_found' }) });
    expect(screen.queryByText(/These rules are not available/)).toBeNull();
    expect(screen.getByRole('alert').textContent).toContain('Not found'); // ErrorView, no Retry on a 404
  });

  it('CK-19 a project that fails to load (backend down) offers Retry; Retry asks again and shows the checks', async () => {
    let tries = 0;
    const { api } = await show('fi', {
      [`GET /api/projects/${PID}`]: () =>
        ++tries === 1 ? reply(502, '<html>Bad gateway</html>') : project,
    });
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(checkCalls(api)).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await flush();
    expect(tries).toBe(2);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(checkCalls(api)).toHaveLength(1);
  });

  it('CK-15 a new pack asks again and shows only the new pack', async () => {
    const other = { ...checks, pack: 'ch', drawings: [] };
    const api = mockApi(
      routes({ [CHECKS]: (c: { url: string }) => (c.url.includes('pack=fi') ? never() : other) }),
    );
    const view = render(
      <InfoProvider>
        <ChecksScreen projectId={PID} pack="fi" />
      </InfoProvider>,
    );
    await flush();
    view.rerender(
      <InfoProvider>
        <ChecksScreen projectId={PID} pack="ch" />
      </InfoProvider>,
    );
    await flush();
    expect(checkCalls(api).map((c) => c.url.split('pack=')[1])).toEqual(['fi', 'ch']);
    expect(screen.getByText('No drawing in this project to check.')).toBeTruthy();
  });

  it('CK-17 the summary table has a caption and column headers; results are a list', async () => {
    await show();
    const table = screen.getByRole('table');
    expect(table.querySelector('caption')).toBeTruthy();
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Rule', 'Passed', 'Failed', 'Cannot tell']);
    const findings = screen.getByRole('region', { name: 'Findings in your files' });
    expect(within(findings).getAllByRole('list')).toHaveLength(1);
  });

  // The screen is styled with Tailwind classes (shadcn migration): the rules live in the component source.
  const tsx = () =>
    readFileSync('src/checks/ChecksScreen.tsx', 'utf8').replace(/\/\/.*|\/\*[\s\S]*?\*\//g, '');

  it('CK-18 the screen names no colour literal; no animation under reduced motion', () => {
    expect(tsx()).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    expect(tsx()).toContain('motion-reduce:[&_*]:transition-none');
  });

  it('CSS: row headers wrap, column headers never break mid-word; the caption is inset from the clipped corner', () => {
    expect(tsx()).toMatch(/scope="row"\s+className="[^"]*whitespace-normal/);
    expect(tsx()).not.toMatch(/scope="col"[^>]*whitespace-normal/); // TableHead is nowrap
    expect(tsx()).toMatch(/<TableCaption className="[^"]*px-4 py-3/);
  });
});
