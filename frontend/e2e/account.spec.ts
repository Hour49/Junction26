// Workspaces screen (docs/specs/frontend/account.md) on the live no-keys backend: AC-25, AC-26, AC-27.
import { expect, test, type Page } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

// No hyphens or spaces: nothing the browser may break the line at (as qa-r1).
const LONG_NAME = 'Hafenstrasse_12_Bauabschnitt_B_Ausfuehrungsplaene_Rev07a.txt';

/** The sample through the API (not the ingest screen, whose wording is its own spec's), read to the end. */
async function sampleDone(page: Page): Promise<string> {
  const started = await page.request.post('/api/projects/sample?fresh=true');
  expect(started.status()).toBe(202);
  const { id } = (await started.json()) as { id: string };
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/projects/${id}`)).json()) as { state: string }).state,
      { timeout: 30_000 },
    )
    .toBe('done');
  return id;
}

test('AC-25 AC-26 AC-27 the workspaces list and the selected one', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const upload = await page.request.post(`/api/projects?name=${encodeURIComponent(LONG_NAME)}`, {
    data: Buffer.from('notes from the site office\n'),
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(upload.status()).toBe(202);
  const id = await sampleDone(page);

  await page.goto('/#/workspaces');
  await expect(page.getByRole('heading', { level: 1, name: 'Your workspaces' })).toBeVisible();
  const items = page.locator('button[aria-pressed]');
  await expect(items.first()).toHaveAttribute('aria-pressed', 'true');
  // Both were made within a second: the backend orders such ties by id, so pick the sample by name.
  const sample = items.filter({ hasText: 'sample-project.zip' }).first();
  await sample.click();
  await expect(sample).toHaveAttribute('aria-pressed', 'true');
  const panel = page.getByRole('region', { name: 'Selected workspace' });
  await expect(panel.getByRole('link', { name: 'Open workspace' })).toHaveAttribute(
    'href',
    `#/p/${id}`,
  );
  const stat = (label: string) => panel.locator('dt', { hasText: label }).locator('+ dd');
  await expect(stat('Files')).toHaveText('11');
  await expect(stat('Drawings')).toHaveText('5');
  await expect(stat('Signed off')).toHaveText(/^0 of \d+$/);
  await expect(panel.getByText('Uploaded sample-project.zip')).toBeVisible();
  await expect(panel.getByText('Analysis done')).toBeVisible();
  await expect(
    panel.getByText(/^Settled by a rule: area of room \(name Küche · 1\.01\)$/),
  ).toBeVisible();

  const listBox = await page.locator('.account-list').boundingBox();
  const panelBox = await panel.boundingBox();
  expect(listBox && panelBox).toBeTruthy();
  if (listBox && panelBox) {
    if (testInfo.project.name === 'phone')
      expect(panelBox.y).toBeGreaterThan(listBox.y + listBox.height - 1);
    else expect(panelBox.x).toBeGreaterThan(listBox.x + listBox.width - 1);
  }
  const columns = await panel
    .locator('dl')
    .evaluate((dl) => getComputedStyle(dl).gridTemplateColumns.split(' ').length);
  expect(columns).toBe(testInfo.project.name === 'phone' ? 2 : 5);
  await shot(page, testInfo, 'account-workspaces', offline);

  // The long name, selected: still no sideways scroll (shot checks it).
  await items.filter({ hasText: LONG_NAME }).first().click();
  await expect(panel.getByRole('heading', { name: LONG_NAME })).toBeVisible();
  await shot(page, testInfo, 'account-long-name', offline);

  await expect(page.locator('body')).not.toContainText(/Beatrice|Hour49|harbour-block-archive/);
  expect(errors).toEqual([]);
});
