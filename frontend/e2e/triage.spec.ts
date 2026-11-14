// File triage end to end (file-triage.md FT-21, FT-14 at 390) on the sample's site photo. It needs a backend with
// triage on: `TRIAGE_CLASSIFIER=rules npx playwright test e2e/triage.spec.ts`; with triage off (the default run) it
// skips itself and the other specs see the sample as before.
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NOTE = 'not described: no description model is set up, so it is not judged';

interface FileRow {
  id: string;
  path: string;
  triage: unknown;
}

test('FT-21: the site photo is set aside as not a floor plan, its trace and issue, then read as a plan', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  const project = (await (await page.request.get(`/api/projects/${pid}`)).json()) as {
    cost_usd: number;
    files: FileRow[];
  };
  const site = project.files.find((f) => f.path === 'photos/site.jpg');
  test.skip(!site?.triage, 'triage is off: run with TRIAGE_CLASSIFIER=rules');
  const fid = site?.id ?? '';
  expect(project.cost_usd).toBe(0);

  // The project screen: the row says what triage thinks, not the reason line.
  await page.goto(`/#/p/${pid}`);
  const files = page.getByRole('region', { name: 'Files' });
  await expect(files).toContainText('1 not a floor plan: kept, not read');
  const row = files.locator(`a[href$="/f/${fid}"]`);
  await expect(row).toContainText('Not a floor plan: not a drawing');
  await expect(row).toContainText('– Not judged');
  await expect(row).not.toContainText('P(plan)');
  await row.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-row', offline);

  // The issues list: one "Not a floor plan" row for it, linking to its trace.
  await page.goto(`/#/p/${pid}/issues`);
  const issue = page.locator('.is-row').filter({ hasText: 'photos/site.jpg' });
  await expect(issue).toHaveCount(1);
  await expect(issue).toContainText('Not a floor plan');
  const call = issue.getByRole('link', { name: 'Make a call' });
  await expect(call).toHaveAttribute('href', `#/p/${pid}/f/${fid}`);
  await issue.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-issue', offline);
  await call.click();

  // The trace: not described, so the note once and no call form; nothing was paid for.
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/f/${fid}$`));
  const card = page.getByRole('region', { name: 'Is it a floor plan?' });
  await expect(
    card.getByRole('heading', { name: 'Not a floor plan: not a drawing' }),
  ).toBeVisible();
  await expect(card.getByText(NOTE, { exact: true })).toHaveCount(1);
  await expect(card.getByText('– Not judged')).toBeVisible();
  await expect(card.getByRole('button', { name: /^It is (not )?related$/ })).toHaveCount(0);
  await expect(card).not.toContainText('Your call replaces the suggestion');
  await expect(page.locator('dt', { hasText: /^Cost$/ }).locator('+ dd')).toHaveText('$0.00');
  const open = page.getByRole('link', { name: 'Open the drawing' });
  await expect(open).toHaveCount(0);
  const name = card.getByRole('textbox', { name: 'Your name' });
  const read = card.getByRole('button', { name: 'Read it as a floor plan' });
  if (testInfo.project.name === 'phone') {
    // FT-14: the name field and the button are tap targets.
    for (const target of [name, read]) {
      expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
  }
  // The upload itself is the only picture of a non-plan (a 1600 px PNG, ~2.4 MB): wait for it before the shot.
  const preview = card.getByRole('img', { name: 'photos/site.jpg as uploaded' });
  await expect
    .poll(() =>
      preview.evaluate(
        (el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth,
      ),
    )
    .toBeGreaterThan(0);
  await card.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-trace', offline);

  // Read it as a floor plan: confirm, then the file is read and its drawing opens.
  await name.fill('Ana');
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toBe("Read photos/site.jpg as a floor plan? This can't be undone.");
    void dialog.accept();
  });
  await read.click();
  await expect(open).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByRole('heading', { name: /^Read as a floor plan on Ana.s call$/ }),
  ).toBeVisible();
  await expect(read).toHaveCount(0);
  await shot(page, testInfo, 'ft-read-as-plan', offline);

  await page.goto(`/#/p/${pid}`);
  await expect(files).toContainText('No image set aside as not a floor plan');
  await expect(row).toContainText(/Read as a floor plan on Ana.s call/);
  expect(errors, 'no console or page errors').toEqual([]);
});
