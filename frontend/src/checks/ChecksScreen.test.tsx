import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it, vi } from 'vitest';
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

  it('CK-2 the pack note renders verbatim; the heading names the pack, country and law', async () => {
    await show();
    expect(screen.getByRole('note').textContent).toBe(NOTE);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(`Pre-check: ${pack.name}`);
    expect(document.body.textContent).toContain(`${pack.country_name} · ${pack.law}`);
  });

  it('CK-4 the summary line counts rules as the conflicts checks row does; the table counts places', async () => {
    const { api } = await show();
    expect(
      screen.getByText('1 rule failed, 1 cannot tell, 1 passed, over 2 drawings'),
    ).toBeTruthy();
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

  it('CK-5/6/7/8 failed then cannot tell per drawing; the cannot-tell look is its own; why and clause shown', async () => {
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
    expect(d2.textContent).toContain('Decree 1/2000 § 2');
    expect(d2.querySelector('blockquote')?.textContent).toBe('Säännös 2.');
    const link = within(d2).getByRole('link', { name: /Read the clause/ });
    expect(link.getAttribute('href')).toBe('https://example.org/decree#s2');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(link.getAttribute('target')).toBe('_blank');
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
    expect(screen.queryByText(FAIL_MEANS)).toBeNull(); // nothing failed: no fail_means
  });

  it("CK-2 the pack's fail_means is shown with the note when a rule failed", async () => {
    await show();
    expect(screen.getByText(FAIL_MEANS)).toBeTruthy();
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
    expect(
      screen.getByText('0 rules failed, 0 cannot tell, 1 passed, over 2 drawings'),
    ).toBeTruthy();
  });

  it('a rule that cannot tell on a drawing without any result gets a "Cannot tell" card with its why and clause', async () => {
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
    expect(card.textContent).toContain('Decree 1/2000 § 1');
    expect(card.textContent).toContain('Not located on the drawing');
    expect(card.textContent).not.toContain('measured');
    expect(screen.queryByText(/nothing these rules apply to/)).toBeNull();
    expect(screen.getByRole('row', { name: /Rule R1/ }).textContent).not.toContain(
      'Does not apply',
    );
    expect(screen.getByRole('row', { name: /Rule R1/ }).textContent).toContain(
      'Cannot tell on 1 drawing: nothing could be read',
    );
    expect(
      screen.getByText('0 rules failed, 1 cannot tell, 0 passed, over 1 drawing'),
    ).toBeTruthy();
  });

  it("Bogdan's fixtures (project_checks.json, info.json rule_packs) render: heading, fail card, file from the payload", async () => {
    const fi = must(bogdanInfo.rule_packs.find((p) => p.id === 'fi'));
    await show('fi', { 'GET /api/info': bogdanInfo, [CHECKS]: bogdanChecks });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(`Pre-check: ${fi.name}`);
    expect(screen.getByRole('note').textContent).toBe(fi.note);
    if (fi.fail_means) expect(screen.getByText(fi.fail_means)).toBeTruthy();
    const d = must(bogdanChecks.drawings[0]);
    expect(screen.getByRole('heading', { name: d.file })).toBeTruthy(); // not in this project's files: the payload's
    const card = must(cards()[0]);
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

  it('"Show on the drawing" scrolls the viewer into view only when it sits under the list; no smooth under reduced motion', async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const media = (wide: boolean, reduced: boolean) => {
      window.matchMedia = vi.fn((q: string) => ({
        matches: q.includes('min-width: 1024px') ? wide : q.includes('reduce') ? reduced : false,
      })) as unknown as typeof window.matchMedia;
    };
    const tap = async () => {
      fireEvent.click(
        within(must(cards()[1])).getByRole('button', { name: /Show on the drawing/ }),
      );
      await flush();
    };
    media(true, false);
    await show();
    await tap();
    expect(scroll).not.toHaveBeenCalled();
    media(false, false);
    await tap();
    expect(scroll).toHaveBeenLastCalledWith({ behavior: 'smooth', block: 'start' });
    expect(scroll.mock.contexts.at(-1)).toBe(document.querySelector('.ck-viewer'));
    media(false, true);
    await tap();
    expect(scroll).toHaveBeenLastCalledWith({ behavior: 'auto', block: 'start' });
  });

  it("CK-9 the drawing heading is this project's file path, never the payload's", async () => {
    const p: ProjectView = {
      ...project,
      files: project.files.map((f) => (f.drawing_id === D2 ? { ...f, path: 'mine/plan.pdf' } : f)),
    };
    const shared = {
      ...checks,
      drawings: checks.drawings.map((d) => ({ ...d, file: 'someone-else/plan.pdf' })),
    };
    await show('fi', { [`GET /api/projects/${PID}`]: p, [CHECKS]: shared });
    expect(screen.getByRole('heading', { name: 'mine/plan.pdf' })).toBeTruthy();
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
    const d2 = must(cards()[1]);
    fireEvent.click(within(d2).getByRole('button', { name: /Show on the drawing/ }));
    await flush();
    fireEvent.click(within(d2).getByRole('button', { name: /Show on the drawing/ }));
    await flush();
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

  it('CK-12 surveyor links carry the takeoff row and every link keeps ?pack=', async () => {
    await show();
    const d2 = must(cards()[1]);
    expect(
      within(d2)
        .getByRole('link', { name: /Open in the surveyor/ })
        .getAttribute('href'),
    ).toBe(`#/p/${PID}/d/${D2}/surveyor?q=door&pack=fi`);
    expect(screen.getByRole('link', { name: /Export issues and plans/ }).getAttribute('href')).toBe(
      `#/p/${PID}/issues?pack=fi`,
    );
    expect(screen.getByRole('heading', { name: fileOf(D2) })).toBeTruthy();
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
    expect(screen.getAllByRole('list', { name: /Places to look at/ }).length).toBeGreaterThan(0);
  });

  it('CK-18 checks.css: tokens only, no animation under reduced motion', () => {
    const css = readFileSync('src/checks/checks.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    expect(css).toMatch(/prefers-reduced-motion: reduce/);
  });

  it('CSS: table headers never break mid-word; the caption is inset from the clipped rounded corner', () => {
    const css = readFileSync('src/checks/checks.css', 'utf8');
    expect(css).toMatch(/\.ck-table th,\s*\.ck-table td \{[^}]*overflow-wrap: normal/);
    expect(css).toMatch(/\.ck-table thead th \{[^}]*white-space: nowrap/);
    expect(css).toMatch(/\.ck-table caption \{[^}]*padding: 12px 16px/);
  });
});
