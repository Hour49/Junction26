// Building-code pre-check (#139) and located issues (#140) on the live sample project, at the project's viewport:
// checks.md CK-16, issues.md IS-19/IS-20, shared.md SH-70, viewer.md VW-79, engineer.md EN-76.
// shortcut: Bogdan's checks/issues endpoints do not exist yet, so /api/info's rule_packs and the checks and issues
// answers come from the hand-made #142 fixtures (src/api/testing.ts) via page.route; switch to the live API when
// his PRs land (delete serveChecks).
import { expect, test, type Page } from '@playwright/test';
import { drawingChecks, issueList, projectChecks, rulePackFi } from '../src/api/testing';
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
  await page.route(/\/api\/projects\/[0-9a-f]+\/issues(\?.*)?$/, (route) =>
    route.fulfill({ json: swap(issueList) }),
  );
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

test('IS-19 IS-20 EN-76: the issues list, the first issue outlined, Open the drawing zooms', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await serveChecks(page, pid);

  for (const query of ['', '?pack=fi']) {
    await page.goto(`/#/p/${pid}/issues${query}`);
    await expect(page.getByRole('heading', { level: 1, name: 'Issues' })).toBeVisible();
    const rows = page.locator('.is-row');
    await expect(rows).toHaveCount(issueList.issues.length);
    // IS-7/IS-19: the first located issue is selected and outlined on its page.
    await expect(rows.first()).toHaveAttribute('aria-current', 'true');
    const where = page.getByRole('region', { name: 'Where' });
    const outlined = where.getByRole('button', { name: /^Mark 1: /, pressed: true });
    await expect(outlined).toBeVisible();
    await expect(outlined).toBeInViewport();
    await noSideScroll(page, `issues${query}`);
    if (testInfo.project.name === 'phone') {
      // IS-20: every row's tap target is at least 44 px tall.
      const heights = await page
        .locator('.is-pick')
        .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
      expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
    }
    await shot(page, testInfo, query ? 'is-issues-fi' : 'is-issues', offline);
  }

  // EN-76: "Open the drawing" opens the engineer at the issue's page and box, zoomed in.
  const first = issueList.issues[0];
  await page.locator('.is-row').first().getByRole('link', { name: 'Open the drawing' }).click();
  await expect(page).toHaveURL(
    new RegExp(`/d/${first?.drawing_id ?? ''}/engineer\\?(.*&)?page=1&box=`),
  );
  await expect(page.getByText(/^(200|400)%$/).first()).toBeVisible();
  await noSideScroll(page, 'engineer focus');
  await shot(page, testInfo, 'is-open-drawing', offline);
  expect(errors, 'no console or page errors').toEqual([]);
});

test('SH-70: no sideways scroll at 390, 768, 1024 and 1440; tabs at least 44 px below 1100', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one sweep over the widths is enough');
  const pid = await sampleDone(page);
  await serveChecks(page, pid);
  const did = issueList.issues[0]?.drawing_id ?? '';
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
