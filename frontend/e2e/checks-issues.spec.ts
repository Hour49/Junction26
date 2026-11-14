// Building-code pre-check (#139) and located issues (#140) on the live sample project, at the project's viewport:
// checks.md CK-16, issues.md IS-19/IS-20, shared.md SH-70, viewer.md VW-79, engineer.md EN-76.
// The issues are the live API (#147). shortcut: the checks endpoints (#139) are not merged, so /api/info's
// rule_packs and the checks answers come from the hand-made #142 fixtures (src/api/testing.ts) via page.route;
// delete serveChecks when #139 lands. Until then ?pack=fi on the issues answers 404 unknown-pack.
import { expect, test, type Page } from '@playwright/test';
import { drawingChecks, projectChecks, rulePackFi } from '../src/api/testing';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NOTE = 'A pre-check of a few rules, not a compliance certificate.';
const FIXTURE_PROJECT = projectChecks.project_id;

/** The fixtures, with the fixture's project id swapped for the live sample's (drawing ids are the sample's). */
async function serveChecks(page: Page, pid: string) {
  const swap = <T>(value: T): T =>
    JSON.parse(JSON.stringify(value).replaceAll(FIXTURE_PROJECT, pid)) as T;
  await page.route('**/api/info', async (route) => {
    const response = await route.fetch();
    const info = (await response.json()) as Record<string, unknown>;
    await route.fulfill({ response, json: { ...info, rule_packs: [rulePackFi] } });
  });
  await page.route(/\/api\/projects\/[0-9a-f]+\/checks(\?.*)?$/, (route) =>
    route.fulfill({ json: swap(projectChecks) }),
  );
  await page.route(/\/api\/drawings\/([0-9a-f]+)\/checks(\?.*)?$/, (route) => {
    const did = /\/api\/drawings\/([0-9a-f]+)\/checks/.exec(route.request().url())?.[1];
    const found = projectChecks.drawings.find((d) => d.drawing_id === did);
    return route.fulfill({ json: found ?? { ...drawingChecks, drawing_id: did, rules: [] } });
  });
}

interface Issue {
  drawing_id: string | null;
  page: number | null;
}

/** The sample's real issues, in the API's order. */
async function liveIssues(page: Page, pid: string): Promise<Issue[]> {
  const response = await page.request.get(`/api/projects/${pid}/issues`);
  expect(response.status()).toBe(200);
  return ((await response.json()) as { issues: Issue[] }).issues;
}

async function noSideScroll(page: Page, where: string) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(
    overflow,
    `${where}: the page scrolls sideways by ${String(overflow)} px`,
  ).toBeLessThanOrEqual(0);
}

const banner = (page: Page) => page.getByRole('banner');

test('CK-16 VW-79: the picker sets ?pack=, the Checks tab, the note verbatim, a fail on the drawing', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await serveChecks(page, pid);

  await page.goto(`/#/p/${pid}`);
  await expect(banner(page).getByRole('link', { name: 'Checks', exact: true })).toHaveCount(0);
  await banner(page)
    .getByRole('button', { name: /^Country rules: / })
    .click();
  await page
    .getByRole('group', { name: 'Building rules the agent follows' })
    .getByRole('button', { name: /Finland/ })
    .click();
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}\\?(.*&)?pack=fi(&.*)?$`));

  await banner(page).getByRole('link', { name: 'Checks', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/checks\\?(.*&)?pack=fi(&.*)?$`));
  const main = page.getByRole('main');
  await expect(main.getByRole('note')).toHaveText(NOTE);
  // VW-79: "Show on the drawing" on the failed place draws it on its page, visible without scrolling.
  await main
    .getByRole('article', { name: 'door 2 · Door clear width' })
    .getByRole('button', { name: 'Show on the drawing' })
    .click();
  const fail = page
    .getByRole('complementary')
    .getByRole('button', { name: /fails the rule/i })
    .first();
  await expect(fail).toBeVisible();
  // At 390 the viewer sits under the list (CK-16): the page scrolls to it; the mark itself needs no scrolling
  // inside the viewer's scroll box (VW-79).
  await page.getByRole('complementary').scrollIntoViewIfNeeded();
  await expect(fail).toBeInViewport();
  await noSideScroll(page, 'checks');
  await shot(page, testInfo, 'ck-checks', offline);
  expect(errors, 'no console or page errors').toEqual([]);
});

test('IS-19 IS-20 EN-76: the issues list, the first issue outlined, Open the drawing at its place', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await serveChecks(page, pid);

  const issues = await liveIssues(page, pid);
  expect(issues.length).toBeGreaterThan(0);

  // Until #139 lands the pack is unknown to the backend: the screen says so instead of a list.
  await page.goto(`/#/p/${pid}/issues?pack=fi`);
  await expect(page.getByRole('heading', { level: 1, name: 'Issues' })).toBeVisible();
  await expect(page.getByText('These country rules are not available.')).toBeVisible();
  await expect(page.locator('.is-row')).toHaveCount(0);
  await noSideScroll(page, 'issues?pack=fi');
  // The header's project list loads on its own: wait, or the shot shows "Loading projects…".
  await expect(banner(page).getByRole('combobox', { name: 'Project' })).not.toContainText(
    'Loading',
  );
  await shot(page, testInfo, 'is-issues-fi', offline);

  await page.getByRole('link', { name: 'Show the issues without country rules' }).click();
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/issues$`));
  const rows = page.locator('.is-row');
  await expect(rows).toHaveCount(issues.length);
  // IS-7/IS-19: the first located issue is selected and outlined on its page.
  await expect(rows.first()).toHaveAttribute('aria-current', 'true');
  const where = page.getByRole('region', { name: 'Where' });
  const outlined = where.getByRole('button', { name: /^Mark 1: /, pressed: true });
  await expect(outlined).toBeVisible();
  await expect(outlined).toBeInViewport();
  // The exports are plain links to the API; the zip downloads once the project is done.
  const main = page.getByRole('main');
  const zip = await main.getByRole('link', { name: 'Export' }).getAttribute('href');
  const csv = await main.getByRole('link', { name: 'CSV only' }).getAttribute('href');
  expect(zip).toMatch(new RegExp(`/api/projects/${pid}/issues\\.zip$`));
  expect(csv).toMatch(new RegExp(`/api/projects/${pid}/issues\\.csv$`));
  const download = await page.request.get(zip ?? '');
  expect(download.status()).toBe(200);
  expect(download.headers()['content-type']).toMatch(/^application\/zip/);
  await noSideScroll(page, 'issues');
  if (testInfo.project.name === 'phone') {
    // IS-20: every row's tap target is at least 44 px tall.
    const heights = await page
      .locator('.is-pick')
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  }
  await shot(page, testInfo, 'is-issues', offline);

  // EN-76: "Open the drawing" opens the engineer at the issue's page with the place outlined. The sample's first
  // issue (Küche, a third of the page wide) needs no zoom: the viewer zooms only boxes under 48 px (viewer.md).
  const first = issues[0];
  await rows.first().getByRole('link', { name: 'Open the drawing' }).click();
  await expect(page).toHaveURL(
    new RegExp(`/d/${first?.drawing_id ?? ''}/engineer\\?(.*&)?page=${String(first?.page)}&box=`),
  );
  const focus = page.locator('.vw-focus').first();
  await expect(focus).toBeVisible();
  await noSideScroll(page, 'engineer focus');
  // Viewport shot with the plan in view (fe-viewer): scroll the page by the toolbar, which is outside the plan's
  // own scroll box, so the focus scroll stays.
  await page.getByRole('button', { name: 'Zoom in' }).first().scrollIntoViewIfNeeded();
  // The zoomed page is a larger image: wait until it has loaded, or the shot shows only the outline.
  const plan = page.getByRole('img', { name: /^Page 1 of / }).first();
  await expect
    .poll(() =>
      plan.evaluate(
        (el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth,
      ),
    )
    .toBeGreaterThan(0);
  await expect(focus).toBeInViewport();
  await shot(page, testInfo, 'is-open-drawing', offline);
  // The one expected error: the browser logs the ?pack=fi 404 (unknown-pack until #139).
  const unexpected = errors.filter((e) => !/status of 404/.test(e));
  expect(errors.length - unexpected.length).toBeLessThanOrEqual(1);
  expect(unexpected, 'no other console or page errors').toEqual([]);
});

test('SH-70: no sideways scroll at 390, 768, 1024 and 1440; tabs at least 44 px below 1100', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one sweep over the widths is enough');
  const pid = await sampleDone(page);
  await serveChecks(page, pid);
  const did = (await liveIssues(page, pid)).find((i) => i.drawing_id)?.drawing_id ?? '';
  const routes = [
    `/#/p/${pid}/checks?pack=fi`,
    `/#/p/${pid}/issues?pack=fi`,
    `/#/p/${pid}/d/${did}/engineer?pack=fi`,
  ];
  for (const [width, height] of [
    [390, 844],
    [768, 1024],
    [1024, 768],
    [1440, 900],
  ] as const) {
    await page.setViewportSize({ width, height });
    for (const route of routes) {
      await page.goto(route);
      await expect(page.getByRole('main')).toBeVisible();
      await expect(banner(page).getByRole('link', { name: 'Checks', exact: true })).toBeVisible();
      await noSideScroll(page, `${route} at ${String(width)}`);
      if (width < 1100) {
        const tabs = await banner(page)
          .getByRole('navigation', { name: 'Views' })
          .getByRole('link')
          .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
        expect(tabs.length).toBeGreaterThan(0);
        expect(Math.min(...tabs), `tabs at ${String(width)}`).toBeGreaterThanOrEqual(44);
      }
    }
  }
});
