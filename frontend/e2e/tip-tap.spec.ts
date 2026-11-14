// The shared Tip on a phone (components/ui/tip.tsx): a tap on a label, number or locked control shows its tip and
// the next tap closes it; a tap on a working control (a link, a button) does what it does and leaves no tip over
// the page. Touch only: the desktop project has no tap.
import { expect, test, type Locator, type Page } from '@playwright/test';
import { sampleDone, shot, watchErrors } from './support';
import { TIPS } from '../src/shell/tips';

test.skip(({ hasTouch }) => !hasTouch, 'taps need the touch project');

/**
 * A tap, returned once its click has run and two frames have painted. A tap's click comes after its focus, and
 * the bug was the click undoing what the focus did: checking before the click would pass on the bug.
 */
async function tap(page: Page, target: Locator) {
  await page.evaluate(() => {
    (window as unknown as { clicked: Promise<void> }).clicked = new Promise((done) => {
      document.addEventListener(
        'click',
        () => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              done();
            });
          });
        },
        { once: true },
      );
    });
  });
  await target.tap();
  await page.evaluate(() => (window as unknown as { clicked: Promise<void> }).clicked);
}

test('a tap on a label shows its tip; a tap elsewhere closes it', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  await page.goto('/#/');
  const formats = page.getByRole('list', { name: 'Formats' });
  await tap(page, formats);
  await expect(formats).toHaveAttribute('data-state', /open/);
  await expect(page.getByRole('tooltip')).toHaveText(TIPS.formats);
  await shot(page, testInfo, 'tip-tap-formats', true);
  await tap(page, page.getByRole('heading').first());
  await expect(formats).toHaveAttribute('data-state', 'closed');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a second tap on the same label closes its tip', async ({ page }) => {
  await page.goto('/#/');
  const formats = page.getByRole('list', { name: 'Formats' });
  await tap(page, formats);
  await expect(formats).toHaveAttribute('data-state', /open/);
  await tap(page, formats);
  await expect(formats).toHaveAttribute('data-state', 'closed');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
});

test('a tap on a working link navigates and leaves no tip', async ({ page }, testInfo) => {
  const id = await sampleDone(page);
  await page.goto(`/#/p/${id}`);
  const through = page
    .locator('dt', { hasText: 'Files through' })
    .locator('[data-slot="tooltip-trigger"]');
  await tap(page, through);
  await expect(through).toHaveAttribute('data-state', /open/);
  await expect(page.getByRole('tooltip')).toHaveText(TIPS.filesThrough);
  await shot(page, testInfo, 'tip-tap-files-through', true);
  const chat = page.getByRole('link', { name: 'Chat', exact: true });
  await tap(page, chat);
  await expect(page).toHaveURL(new RegExp(`#/p/${id}/chat$`));
  await expect(chat).toHaveAttribute('data-state', 'closed');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  await shot(page, testInfo, 'tip-tap-after-link', true);
});
