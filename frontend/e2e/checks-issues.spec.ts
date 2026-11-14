// Building-code pre-check (#139) and located issues (#140) on the live sample project, at the project's viewport:
// checks.md CK-16, issues.md IS-19/IS-20, shared.md SH-70, viewer.md VW-79, engineer.md EN-76.
// Everything is the live no-keys backend: real rule packs (fi, ch-zh; #139), checks and issues (#147).
import { expect, test, type Page } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NOTE = 'A pre-check of a few rules, not a compliance certificate.';

interface CheckResult {
  status: string;
  marks?: unknown[] | null;
}

/** The sample's real check results with ?pack=fi, flattened over drawings and rules. */
async function liveResults(page: Page, pid: string): Promise<CheckResult[]> {
  const response = await page.request.get(`/api/projects/${pid}/checks?pack=fi`);
  expect(response.status()).toBe(200);
  const body = (await response.json()) as {
    note: string;
    drawings: { rules: { results: CheckResult[] }[] }[];
  };
  expect(body.note).toBe(NOTE);
  return body.drawings.flatMap((d) => d.rules.flatMap((r) => r.results));
}

interface Issue {
  drawing_id: string | null;
  page: number | null;
}

/** The sample's real issues, in the API's order. */
async function liveIssues(page: Page, pid: string, query = ''): Promise<Issue[]> {
  const response = await page.request.get(`/api/projects/${pid}/issues${query}`);
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

test('CK-16 VW-79: the picker sets ?pack=, the Checks tab, the note verbatim, a located result on the drawing', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);

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
  // The sample's rooms carry German names (Küche, Zimmer) the packs do not type, so today no result is located
  // (flat-a/flat-b not applicable, the scans and the model cannot tell). Assert whatever the API gives.
  const located = (await liveResults(page, pid)).filter((r) => (r.marks ?? []).length > 0);
  const show = main.getByRole('button', { name: /Show on the drawing/ });
  if (located.length === 0) {
    await expect(show).toHaveCount(0);
  } else {
    // VW-79: "Show on the drawing" draws the place on its page, visible without scrolling.
    await show.first().click();
    const mark = page
      .getByRole('complementary')
      .getByRole('button', { name: /^Mark \d+: / })
      .first();
    await expect(mark).toBeVisible();
    // At 390 the viewer sits under the list (CK-16): the page scrolls to it; the mark itself needs no
    // scrolling inside the viewer's scroll box (VW-79).
    await page.getByRole('complementary').scrollIntoViewIfNeeded();
    await expect(mark).toBeInViewport();
  }
  await noSideScroll(page, 'checks');
  await shot(page, testInfo, 'ck-checks', offline);

  // The second real pack (canton of Zürich): its own heading, the same note.
  await page.goto(`/#/p/${pid}/checks?pack=ch-zh`);
  await expect(main.getByRole('heading', { level: 1, name: /Zürich/ })).toBeVisible();
  await expect(main.getByRole('note')).toHaveText(NOTE);
  await noSideScroll(page, 'checks ch-zh');
  await shot(page, testInfo, 'ck-checks-ch-zh', offline);
  expect(errors, 'no console or page errors').toEqual([]);
});

test('IS-19 IS-20 EN-76: the issues list, the first issue outlined, Open the drawing at its place', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);

  // With a pack the list carries its failed checks too (none on today's sample), so it is the API's own list.
  const withPack = await liveIssues(page, pid, '?pack=fi');
  await page.goto(`/#/p/${pid}/issues?pack=fi`);
  await expect(page.getByRole('heading', { level: 1, name: 'Issues' })).toBeVisible();
  await expect(page.locator('.is-row')).toHaveCount(withPack.length);
  await expect(page.getByText('These country rules are not available.')).toHaveCount(0);
  await noSideScroll(page, 'issues?pack=fi');
  // The header's project list loads on its own: wait, or the shot shows "Loading projects…".
  await expect(banner(page).getByRole('combobox', { name: 'Project' })).not.toContainText(
    'Loading',
  );
  await shot(page, testInfo, 'is-issues-fi', offline);

  const issues = await liveIssues(page, pid);
  expect(issues.length).toBeGreaterThan(0);
  await page.goto(`/#/p/${pid}/issues`);
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
  expect(errors, 'no console or page errors').toEqual([]);
});

test('SH-70: no sideways scroll at 390, 768, 1024 and 1440; tabs at least 44 px below 1100', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one sweep over the widths is enough');
  const pid = await sampleDone(page);
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
