// The lanes' file names in a real browser (ingest.md IN-113, IN-129): a folder that gives way keeps its first letter
// and a whole "…/", never a few pixels of a cut glyph (trace's final e2e, 2026-11-15: "scans/ground-floor-copy.png"
// at 390), nor a lone letter that reads as a folder ("s/": Chromium shows the first letter, not "…", in 1ch).
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

test('IN-113: a lane folder is shown whole or as at least "s…/", at every width', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await page.goto(`/#/p/${pid}`);
  const lanes = page.getByRole('region', { name: 'Routes' });
  const copy = lanes.getByRole('link', { name: 'scans/ground-floor-copy.png' });
  await expect(copy).toBeVisible();
  // per folder: its width, whether its text fits, and what its first letter and "…/" take in its own font
  const folders = await lanes.locator('.ingest-folder').evaluateAll((spans) =>
    spans.map((span) => {
      const probe = document.createElement('span');
      probe.textContent = `${(span.textContent ?? '').slice(0, 1)}…/`;
      probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre';
      span.appendChild(probe);
      const least = probe.getBoundingClientRect().width;
      probe.remove();
      const box = span.getBoundingClientRect().width;
      const whole = [span, ...span.querySelectorAll('*')].every(
        (e) => e.scrollWidth <= e.clientWidth,
      );
      return { path: span.closest('a')?.getAttribute('aria-label'), box, least, whole };
    }),
  );
  expect(folders.length).toBeGreaterThan(0);
  for (const f of folders) {
    // cut: never narrower than "s…/" (a 0.5 px rounding allowance)
    if (!f.whole)
      expect(f.box, `${String(f.path)}: folder ${String(f.box)} px`).toBeGreaterThanOrEqual(
        f.least - 0.5,
      );
  }
  // the name's end and extension stay whole beside it
  await expect(copy.locator('.ingest-name-end')).toHaveText('oor-copy.png');
  const end = await copy
    .locator('.ingest-name-end')
    .evaluate((e) => e.scrollWidth <= e.clientWidth);
  expect(end).toBe(true);
  await copy.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'lane-names', offline);
  expect(errors).toEqual([]);
});
