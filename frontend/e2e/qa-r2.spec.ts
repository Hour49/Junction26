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

  // The read-as note is on the card itself, with Details still closed (#14 R2).
  const details = turn.locator('details');
  await expect(details).not.toHaveAttribute('open');
  const note = turn.getByText("Read 'mnay' as 'many'", { exact: true });
  await expect(note).toBeVisible();
  const box = await note.boundingBox();
  const width = page.viewportSize()?.width ?? 0;
  expect(
    box && box.x >= 0 && box.x + box.width <= width,
    'the note lies within the viewport width',
  ).toBe(true);

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

// R2-qa-1-3: a sum of several rooms; its number badges must not overlap each other.
const SUM = 'What is the net floor area of all indoor rooms in m²?';

test('R2-qa-1-3: area badges do not overlap', async ({ page }, testInfo) => {
  await startSample(page);
  await page.locator('a[href*="/f/f"]').filter({ hasText: 'plans/flat-b.pdf' }).click();
  await page.getByRole('link', { name: 'Open the drawing' }).click();
  await page.getByRole('textbox', { name: 'Question' }).fill(SUM);
  await page.getByRole('button', { name: 'Ask' }).click();
  const turn = page.getByRole('article', { name: SUM }).last();
  await expect(turn.getByTestId('answer-value')).toBeVisible();
  const badges = turn.getByRole('button', { name: /^Mark \d+:/ });
  await expect(badges.first()).toBeVisible();
  await badges.first().scrollIntoViewIfNeeded();
  const boxes = (
    await Promise.all((await badges.all()).map((badge) => badge.boundingBox()))
  ).filter((box) => box !== null);
  expect(boxes.length, 'badges on the page').toBeGreaterThanOrEqual(3);
  const overlaps: string[] = [];
  boxes.forEach((a, i) => {
    boxes.slice(i + 1).forEach((b, j) => {
      const apart =
        a.x + a.width <= b.x ||
        b.x + b.width <= a.x ||
        a.y + a.height <= b.y ||
        b.y + b.height <= a.y;
      if (!apart) overlaps.push(`badge ${String(i + 1)} and ${String(i + j + 2)}`);
    });
  });
  expect(overlaps, 'overlapping badges').toEqual([]);
  await shot(
    page,
    testInfo,
    `qa-r2-labels-${String(page.viewportSize()?.width)}`,
    await noKeys(page),
  );
});
