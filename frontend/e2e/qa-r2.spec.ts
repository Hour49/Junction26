// QA round 2 (#80): the template parser reads a misspelt question and says so in the answer's explanation. On the
// live no-keys backend, at both widths.
import { expect, test } from '@playwright/test';
import { noKeys, shot, startSample } from './support';

// The backend reads 'mnay' as 'many' (explanation "read 'mnay' as 'many'"), checked on the e2e backend.
const TYPO = 'How mnay doors are there?';

test('R2: a misspelt question shows how it was read', async ({ page }, testInfo) => {
  await startSample(page);
  await page.locator('a[href*="/f/f"]').filter({ hasText: 'plans/flat-b.pdf' }).click();
  await page.getByRole('link', { name: 'Open the drawing' }).click();
  await expect(page).toHaveURL(/\/d\/[0-9a-f]{16}\/engineer$/);

  await page.getByRole('textbox', { name: 'Question' }).fill(TYPO);
  await page.getByRole('button', { name: 'Ask' }).click();
  const turn = page.getByRole('article', { name: TYPO }).last();
  await expect(turn.getByTestId('answer-value')).toHaveText('2');

  await turn.getByText('Details', { exact: true }).click();
  const how = turn.getByText(/^How: /);
  await expect(how).toBeVisible();
  await expect(how).toHaveText(/^How: read '/);
  await expect(how).toContainText("read 'mnay' as 'many'");
  await how.scrollIntoViewIfNeeded();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, 'horizontal page overflow in px').toBeLessThanOrEqual(0);
  await shot(
    page,
    testInfo,
    `qa-r2-typo-${String(page.viewportSize()?.width)}`,
    await noKeys(page),
  );
});
