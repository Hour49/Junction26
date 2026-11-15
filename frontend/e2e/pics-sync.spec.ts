// The plan edit followed onto a real-looking floor's services pictures (brief pics/pic-sync): a ZIP made by
// backend/scripts/pics_demo_zip.py from the DigitalHub models (partner data: never in git, so the ZIP is passed by
// path). Run: `DISCIPLINE_PICTURES=template (or gemini, with GEMINI_API_KEY) SERVICES_FOLLOW=on PICS_ZIP=<zip> npx playwright test
// e2e/pics-sync.spec.ts`; PICS_REMOVE overrides the wall asked for. Skips itself without them. Screenshots in
// screenshots/<project>/pics-sync-*.png.
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

const ZIP = process.env.PICS_ZIP ?? '';
test.skip(
  !['template', 'gemini'].includes(process.env.DISCIPLINE_PICTURES ?? '') ||
    process.env.SERVICES_FOLLOW !== 'on' ||
    !ZIP,
  'run with DISCIPLINE_PICTURES=template|gemini SERVICES_FOLLOW=on PICS_ZIP=<zip>',
);

// With the rooms' numbers: the rules planner (no keys) matches a multi-word name only with its number
// (chat_rules._named); without them it asks which wall. W36: plumbing runs inside it and a radiator sits on it
// (offline probe with DISCIPLINE_PICTURES=gemini), so every sheet has marks.
const REMOVE =
  process.env.PICS_REMOVE ??
  'Remove the wall between WC Damen West - EG 1.15 and WC Herren West - EG 1.16';

test('sync: a wall removed on the plan, then each discipline sheet with the edit on it', async ({
  page,
}, testInfo) => {
  test.setTimeout(300_000);
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const started = await page.request.post('/api/projects?name=pics-digitalhub.zip', {
    data: readFileSync(ZIP),
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(started.status()).toBe(202);
  const { id } = (await started.json()) as { id: string };
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/projects/${id}`)).json()) as { state: string }).state,
      { timeout: 240_000, intervals: [2_000] },
    )
    .toBe('done');
  await page.goto(`/#/p/${id}/chat`);
  await page.getByRole('textbox', { name: 'Question' }).fill(REMOVE);
  await page.getByRole('button', { name: 'Ask' }).click();
  const card = page.getByRole('article', { name: REMOVE }).last().locator('.ag-card--edit');
  await expect(card).toBeVisible({ timeout: 60_000 });
  await shot(page, testInfo, 'pics-sync-plan', offline);
  const tabs = card.getByRole('group', { name: 'Discipline' });
  for (const name of ['Heating', 'Plumbing']) {
    const tab = tabs.getByRole('button', { name: new RegExp(`^${name}`) });
    await tab.click();
    console.log(`${testInfo.project.name} ${name}: ${(await tab.textContent()) ?? ''}`);
    console.log(`  ${(await card.locator('.ms-pairing, .ms-line').allTextContents()).join(' | ')}`);
    // the sheet itself in view (the card is taller than the screen), once its page has loaded
    await card.locator('.ag-planbox img').waitFor();
    await card.locator('.ag-planbox').scrollIntoViewIfNeeded();
    await shot(page, testInfo, `pics-sync-${name.toLowerCase()}`, offline);
  }
  // AC-45: the plan and both pictures side by side, the edit on each
  await tabs.getByRole('button', { name: 'All sheets' }).click();
  await expect(card.locator('.ms-sync-panel img')).toHaveCount(3, { timeout: 30_000 });
  await card.locator('.ms-sync').scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'pics-sync-all', offline);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
