// The surveyor's e2e criteria the golden path does not walk (surveyor.md SV-47, SV-48: reject and restore a door,
// undo a sign-off), on the live no-keys backend.
import { expect, test, type Page } from '@playwright/test';
import { noKeys, shot, startSample, watchErrors } from './support';

async function openSurveyor(page: Page) {
  await startSample(page);
  await page.locator('a[href*="/f/f"]').filter({ hasText: 'plans/flat-b.pdf' }).click();
  await page.getByRole('link', { name: 'Open the drawing' }).click();
  await page.getByRole('link', { name: 'Surveyor', exact: true }).click();
  await expect(page).toHaveURL(/\/d\/[0-9a-f]{16}\/surveyor/);
}

test('SV-47, SV-48: reject and restore a door, sign off and undo', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  await openSurveyor(page);
  await expect(page.getByRole('table', { name: 'To review' })).toContainText(
    'area of room (name 1.01)',
  );
  await shot(page, testInfo, 'surveyor-1-open', offline);

  const door = page
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name: 'door count', exact: true }) });
  await door.getByRole('button', { name: 'door count', exact: true }).click();
  await expect(door.getByRole('cell').first()).toHaveText('2');
  const marks = page.getByRole('list', { name: 'Marks' });

  await marks.getByRole('listitem').nth(1).getByRole('button', { name: 'Reject' }).click();
  await expect(door.getByRole('cell').first()).toContainText('1');
  await expect(door).toContainText('Changed in review');
  await shot(page, testInfo, 'surveyor-2-rejected', offline);

  await marks.getByRole('listitem').nth(1).getByRole('button', { name: 'Restore' }).click();
  await expect(door.getByRole('cell').first()).toHaveText('2');

  await page.getByRole('textbox', { name: 'Signing as' }).fill('Ana');
  await page.getByRole('button', { name: 'Sign off 2' }).click();
  await expect(door).toContainText('Verified');
  await page.getByRole('button', { name: 'Undo sign-off' }).click();
  await expect(door).not.toContainText('Verified');
  await expect(page.getByRole('button', { name: 'Sign off 2' })).toBeVisible();
  await shot(page, testInfo, 'surveyor-3-undone', offline);

  expect(errors, 'console or page errors').toEqual([]);
});
