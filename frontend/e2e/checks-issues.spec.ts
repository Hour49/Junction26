// Building-code pre-check (#139) and located issues (#140) on the live sample project, at the project's viewport:
// checks.md CK-16, issues.md IS-19/IS-20, shared.md SH-70, viewer.md VW-79, engineer.md EN-76.
// Everything is the live no-keys backend: real rule packs (fi, ch-zh; #139), checks and issues (#147).
import { expect, test, type Page } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NOTE = 'A pre-check of a few rules, not a compliance certificate.';

interface CheckResult {
  status: string;
  subject: { label: string | null };
  marks?: unknown[] | null;
}

/** The sample's real check results for a pack, flattened over drawings and rules. */
async function liveResults(page: Page, pid: string, pack: string): Promise<CheckResult[]> {
  const response = await page.request.get(`/api/projects/${pid}/checks?pack=${pack}`);
  expect(response.status()).toBe(200);
  const body = (await response.json()) as {
    note: string;
    drawings: { rules: { results: CheckResult[] }[] }[];
  };
  expect(body.note).toBe(NOTE);
  return body.drawings.flatMap((d) => d.rules.flatMap((r) => r.results));
}

interface Issue {
  kind: string;
  drawing_id: string | null;
  page: number | null;
  severity: string;
  state: string;
  resolved?: unknown;
  answer?: unknown;
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

test('CK-16 VW-79 DOC-16: the picker sets ?pack= and links to the checks, no note, the ch-zh fail outlined in a dialog', async ({
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

  // No Checks tab (SH-75): the country picker links to the checks, keeping the pack.
  await banner(page)
    .getByRole('button', { name: /^Country rules: / })
    .click();
  await page
    .getByRole('group', { name: 'Building rules the agent follows' })
    .getByRole('link', { name: 'Building construction rules' })
    .click();
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/checks\\?(.*&)?pack=fi(&.*)?$`));
  const main = page.getByRole('main');
  await expect(main.getByRole('note')).toHaveCount(0);
  // Codecheck/sample-rooms: the sample's bedroom "Zimmer 1.05" is typed. fi (>= 7 m²) passes it on both flats,
  // so nothing fails and the three flats (flat-c has no bedroom) count as passing.
  const fi = await liveResults(page, pid, 'fi');
  expect(fi.filter((r) => r.status === 'fail')).toEqual([]);
  expect(fi.some((r) => r.status === 'pass' && r.subject.label === 'Zimmer 1.05')).toBe(true);
  await expect(main.getByText('3 drawings pass every checked place')).toBeVisible();
  await expect(main.getByRole('article', { name: /^Zimmer 1\.05 · / })).toHaveCount(0);
  await noSideScroll(page, 'checks');
  await shot(page, testInfo, 'ck-checks', offline);

  // ch-zh (>= 10 m²): flat-b's 8.06 m² bedroom is the sample's one failed rule.
  const zh = await liveResults(page, pid, 'ch-zh');
  expect(zh.filter((r) => r.status === 'fail').map((r) => r.subject.label)).toEqual([
    'Zimmer 1.05',
  ]);
  await page.goto(`/#/p/${pid}/checks?pack=ch-zh`);
  await expect(main.getByRole('heading', { level: 1, name: /Zürich/ })).toBeVisible();
  await expect(main.getByRole('note')).toHaveCount(0);
  const findings = main.getByRole('region', { name: 'Findings in your files' });
  const fail = findings.getByRole('article', {
    name: /^Zimmer 1\.05 · A bedroom or living room is at least 10 m2/,
  });
  await expect(fail).toHaveCount(1);
  await expect(fail).toContainText('Fails');
  await expect(fail).toContainText('File: plans/flat-b.pdf');
  await expect(fail).toContainText('8.06');
  await expect(main.getByText('2 drawings pass every checked place')).toBeVisible();
  await noSideScroll(page, 'checks ch-zh');
  await shot(page, testInfo, 'ck-checks-ch-zh', offline);
  // VW-79: "Show on the drawing" opens the drawing in a dialog with the failed room outlined, visible without
  // scrolling the page; Close shuts it.
  await fail.getByRole('button', { name: 'Show on the drawing' }).click();
  const dialog = page.getByRole('dialog', { name: 'plans/flat-b.pdf' });
  const mark = dialog.getByRole('button', { name: /fails the rule/ }).first();
  await expect(mark).toBeVisible();
  await expect(mark).toBeInViewport();
  await shot(page, testInfo, 'ck-checks-ch-zh-dialog', offline);
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(dialog).toHaveCount(0);
  expect(errors, 'no console or page errors').toEqual([]);
});

test('DOC IS-19 IS-20 P6a: Documents lists no issues; its tab badge still counts them, with and without a pack', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  const main = page.getByRole('main');

  // ch-zh: flat-b's bedroom fails, the one issue that needs an answer; answering it moves into the chat, so
  // Documents only counts it on the tab.
  await page.goto(`/#/p/${pid}/documents?pack=ch-zh`);
  await expect(main.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
  await expect(main.getByRole('region', { name: 'Issues on demand' })).toHaveCount(0);
  await expect(main.getByRole('textbox')).toHaveCount(0);
  await expect(banner(page).getByRole('link', { name: /^Documents/ })).toHaveAccessibleName(
    'Documents, 1 issue to answer',
  );
  await expect(main.getByRole('link', { name: 'Export' })).toHaveCount(0);
  await noSideScroll(page, 'documents?pack=ch-zh');
  await shot(page, testInfo, 'is-issues-ch-zh', offline);

  // fi passes those rooms: nothing to answer.
  await page.goto(`/#/p/${pid}/documents?pack=fi`);
  await expect(main.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
  await expect(main.getByRole('region', { name: 'Issues on demand' })).toHaveCount(0);
  await noSideScroll(page, 'documents?pack=fi');
  // ui-bugs 10, 11: the header has no project picker and no Workspaces link.
  await expect(banner(page).getByRole('combobox')).toHaveCount(0);
  await expect(banner(page).getByRole('link', { name: 'Workspaces' })).toHaveCount(0);
  await shot(page, testInfo, 'is-issues-fi', offline);

  // No pack: no export either.
  await page.goto(`/#/p/${pid}/documents`);
  await expect(main.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
  await expect(main.getByRole('link', { name: 'Export' })).toHaveCount(0);
  await noSideScroll(page, 'documents');
  await shot(page, testInfo, 'is-issues', offline);
  expect(errors, 'no console or page errors').toEqual([]);
});

test('SH-70 SH-83: no sideways scroll at 390, 768, 1024 and 1440; tabs at least 44 px below 1100', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one sweep over the widths is enough');
  const pid = await sampleDone(page);
  const did = (await liveIssues(page, pid)).find((i) => i.drawing_id)?.drawing_id ?? '';
  const routes = [
    `/#/p/${pid}/checks?pack=fi`,
    `/#/p/${pid}/documents?pack=fi`,
    `/#/p/${pid}/chat?pack=fi`,
    `/#/about?project=${pid}`,
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
      await noSideScroll(page, `${route} at ${String(width)}`);
      if (width < 1100 && !route.startsWith('/#/about')) {
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
