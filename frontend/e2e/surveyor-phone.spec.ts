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

// R3-B8: at 390 px the fixed Value and State columns left the quantity name ~80 px, so names broke inside words
// ("COMMO" / "N AREA)"). Every word of every name must fit on one line of its cell.
test('R3-B8: on a phone no quantity name breaks inside a word', async ({ page }, testInfo) => {
  const offline = await noKeys(page);
  await openSurveyor(page);
  const names = page.locator('.sv-table tbody th[scope="row"] button');
  await expect(names.first()).toBeVisible();
  const tooWide = await names.evaluateAll((buttons) => {
    const ctx = document.createElement('canvas').getContext('2d');
    if (!ctx) return ['no canvas'];
    return buttons.flatMap((b) => {
      const cs = getComputedStyle(b);
      ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const room = b.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      return b.textContent
        .split(/\s+/)
        .filter((w) => ctx.measureText(w).width > room)
        .map(
          (w) =>
            `${w} (${String(Math.round(ctx.measureText(w).width))} > ${String(Math.round(room))} px)`,
        );
    });
  });
  await shot(page, testInfo, 'surveyor-r3b8-names', offline);
  expect(tooWide, 'words wider than their cell').toEqual([]);
});

// R3-G9: on a phone each quantity is a card: the name across the card's full width on top, the value and the state
// on one line under it; the page never scrolls sideways.
test('R3-G9: on a phone the takeoff is one card per quantity', async ({ page }, testInfo) => {
  const offline = await noKeys(page);
  await openSurveyor(page);
  const rows = page.locator('.sv-table tbody tr[data-key]');
  await expect(rows.first()).toBeVisible();
  const cards = await rows.evaluateAll((trs) =>
    trs.map((tr) => {
      const [name, value, state] = [...tr.children].map((c) => c.getBoundingClientRect());
      const card = tr.getBoundingClientRect();
      return {
        nameFull: !!name && name.width >= card.width - 40,
        under:
          !!name &&
          !!value &&
          !!state &&
          value.top >= name.bottom - 1 &&
          state.top >= name.bottom - 1,
        oneLine: !!value && !!state && Math.abs(value.top - state.top) < 12,
      };
    }),
  );
  await rows.first().scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'surveyor-r3g9-cards', offline);
  expect(cards.filter((c) => !c.nameFull || !c.under || !c.oneLine)).toEqual([]);
  const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(wide, 'no sideways scroll').toBeLessThanOrEqual(0);
});

// R4-E10: at 390 the detail sat under all 81 rows, ~5,700 px below the plan and its numbered marks. Now a tap on a
// row brings the plan into view with the detail right under it, before the lists.
test('R4-E10: on a phone a tapped quantity shows the plan with its detail right under it', async ({
  page,
}, testInfo) => {
  const offline = await noKeys(page);
  await openSurveyor(page);
  const row = page.getByRole('button', { name: 'window count', exact: true });
  await row.scrollIntoViewIfNeeded();
  await row.tap();
  const detail = page.getByRole('region', { name: 'Selected quantity' });
  await expect(detail).toContainText('window count');
  const plan = page.locator('.vw').first();
  await expect.poll(async () => (await plan.boundingBox())?.y ?? -1).toBeGreaterThanOrEqual(0); // the plan is on screen, under the sticky header
  const planBox = await plan.boundingBox();
  const detailBox = await detail.boundingBox();
  const table = await page.getByRole('table', { name: 'To review' }).boundingBox();
  expect(detailBox && planBox && detailBox.y > planBox.y).toBe(true);
  expect(detailBox && table && detailBox.y < table.y).toBe(true);
  expect(planBox && planBox.y < (page.viewportSize()?.height ?? 0)).toBe(true);
  await shot(page, testInfo, 'surveyor-r4e10-detail-under-plan', offline);
});
