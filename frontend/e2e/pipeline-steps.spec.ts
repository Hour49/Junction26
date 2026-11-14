// The pipeline steps as the backend runs them (ingest.md "Pipeline steps v4" IN-91, advanced-ingest.md AV-46,
// AV-48): the finished sample on Simple and Advanced, with screenshots at the project's viewport.
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NAMES = [
  'Unpack',
  'Identify',
  'Route',
  'Normalise',
  'Extract',
  'Second count',
  'Takeoff',
  'Store',
  'Index',
];

test('IN-91, AV-46, AV-48: the nine steps on Simple and Advanced', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);

  await page.goto(`/#/p/${pid}`);
  const list = page.getByRole('list', { name: 'Steps' });
  await expect(page.getByText('All 9 steps done').first()).toBeVisible();
  await expect(list.locator('.ingest-step-name')).toHaveText(NAMES);
  await list.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ingest-steps', offline);

  await page.goto(`/#/p/${pid}?view=advanced`);
  const rail = page.getByRole('navigation', { name: 'Steps' });
  await expect(rail.getByRole('button')).toHaveCount(9);
  for (const [i, name] of NAMES.entries())
    await expect(rail.getByRole('button').nth(i)).toContainText(name);
  await rail.getByRole('button', { name: /^Extract/ }).click();
  // the sample has an IFC model, drawn PDFs and images: one line per route, BIM model first
  await expect(page.getByRole('list', { name: 'By route' }).getByRole('listitem')).toHaveText([
    /^BIM model route: /,
    /^drawn PDF route: /,
    /^image route: /,
  ]);
  await shot(page, testInfo, 'advanced-steps', offline);
  await rail.getByRole('button', { name: /^Index/ }).click();
  await expect(
    page.getByRole('heading', { level: 2, name: 'Indexing for questions' }),
  ).toBeVisible();
  await shot(page, testInfo, 'advanced-index', offline);
  expect(errors).toEqual([]);
});
