// K3 (docs/KNOWN.md): on a phone the surveyor's drawings and conflicts list came first, full length, and the drawing
// started below the fold. At <= 640 px the list folds behind one toggle with both counts; the drawing comes first.
import { expect, test } from '@playwright/test';
import { noKeys, openSurveyor, shot, watchErrors } from './support';

test.skip(({ isMobile }) => !isMobile, 'the phone layout');

test('K3: on a phone the drawing starts above the fold and the lists open from one toggle', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  await openSurveyor(page);
  const frame = page.locator('.vw-frame').first();
  await expect(frame).toBeVisible();
  const top = (await frame.boundingBox())?.y ?? Infinity;
  const fold = page.viewportSize()?.height ?? 0;
  expect(top, 'the drawing starts above the fold').toBeLessThan(fold * 0.6);
  const drawings = page.getByRole('list', { name: /^Drawings/ });
  await expect(drawings).toBeHidden();
  await shot(page, testInfo, 'surveyor-k3-folded', offline);

  const toggle = page.getByRole('button', { name: /^Drawings \(\d+\) · Conflicts \(\d+\)$/ });
  await toggle.tap();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(drawings).toBeVisible();
  await shot(page, testInfo, 'surveyor-k3-open', offline);
  expect(errors, 'console or page errors').toEqual([]);
});
